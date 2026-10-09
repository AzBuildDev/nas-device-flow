#!/usr/bin/env python3
"""Temporary NAS browser installer. Never uses Docker socket or starts DHCP."""
import hmac
import http.cookies
import ipaddress
import json
import os
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from install import Settings, address_available, ip_json, occupied_addresses, usable_lans
from initialize import bootstrap
from subscriptions import validate_url

PROJECT = Path(os.environ.get('NDF_SETUP_WORKSPACE', '/workspace'))
HOST_PROJECT = os.environ.get('NDF_PROJECT_PATH', '')
PORT = int(os.environ.get('NDF_SETUP_PORT', '9088'))
CODE = secrets.token_urlsafe(18)
SESSIONS = {}
FAILURES = {}
LOCK = threading.RLock()
HTML = Path(__file__).with_name('setup.html')
TEMPLATE = Path(os.environ.get('NDF_COMPOSE_TEMPLATE', '/app/compose.template.yaml'))


def snapshot():
    addresses = ip_json('-d', 'address', 'show')
    routes = ip_json('-4', 'route', 'show', 'default')
    neighbors = ip_json('-4', 'neighbor', 'show')
    return addresses, usable_lans(addresses, routes), occupied_addresses(addresses, neighbors)


def public_detection():
    addresses, lans, known = snapshot()
    installed = None
    if (PROJECT / 'deployment.compose.yaml').exists():
        config = json.loads((PROJECT / 'runtime/control-center/settings.json').read_text())
        installed = {'panel_origin': config['panel_origin'], 'core_ip': config['core_ip']}
    return {'lans': lans, 'folder': HOST_PROJECT, 'exists': existing_state(), 'installed': installed}


def existing_state():
    return any(os.path.lexists(PROJECT / name) for name in ('.env', 'runtime', 'deployment.compose.yaml'))


def validate_network(body, probe=address_available):
    """Validate against host-derived interfaces; check address conflicts before committing."""
    addresses, lans, known = snapshot()
    lan = next((lan for lan in lans if lan['parent'] == body.get('parent') and lan['subnet'] == body.get('subnet')
                and lan['nas_ip'] == body.get('nas_ip')), None)
    if lan is None:
        raise ValueError('network_changed')
    allowed = ('subnet', 'upstream', 'core_ip', 'panel_ip', 'dhcp_start', 'dhcp_end')
    config = {key: body.get(key) for key in allowed}
    if not all(isinstance(value, str) for value in config.values()):
        raise ValueError('invalid_config')
    network = ipaddress.ip_network(config['subnet'])
    # Preserve every NAS address in this LAN, including aliases, outside the future pool.
    host_ips = {ip for ip in occupied_addresses(addresses, []) if ipaddress.ip_address(ip) in network}
    extras = body.get('infrastructure', [])
    if not isinstance(extras, list) or not all(isinstance(x, str) for x in extras):
        raise ValueError('invalid_config')
    config.update(infrastructure=sorted(host_ips | set(extras)),
                  panel_origin=f"http://{config['panel_ip']}:9080", dhcp_authoritative=False)
    settings = Settings(**config)
    if {settings.upstream, settings.core_ip, settings.panel_ip} & host_ips:
        raise ValueError('address_conflict')
    if body.get('fixed_nas') is not True or body.get('reserved_ips') is not True:
        raise ValueError('confirm_addresses')
    warnings = []
    for address in (settings.core_ip, settings.panel_ip):
        result = probe(lan['parent'], address, known)
        if result is False:
            raise ValueError('address_conflict')
        if result is None:
            warnings.append('arp_unavailable')
    if warnings and body.get('manual_ip_check') is not True:
        raise ValueError('arp_unavailable')
    if lan['ipv6']:
        warnings.append('ipv6')
    return config, lan['parent'], sorted(set(warnings))


def deployment_compose(config, parent, template=None, folder=None):
    """Render a standalone NAS-GUI project with absolute volumes and no build step."""
    template = TEMPLATE if template is None else template
    folder = HOST_PROJECT if folder is None else folder
    if not folder.startswith('/') or any(c in folder for c in ('\n', '\r', '\x00', '$')):
        raise ValueError('invalid_folder')
    compose = yaml.safe_load(Path(template).read_text())
    services = compose['services']
    services['controller'].pop('build', None)
    services['controller']['image'] = 'ghcr.io/azbuilddev/nas-device-flow-controller:0.1.0'
    # Use the release's pinned core image; do not carry ${...} into a GUI import.
    services['mihomo']['image'] = services['mihomo']['image'].split(':-', 1)[1].removesuffix('}')
    for name, address, target in (('mihomo', config['core_ip'], '/root/.config/mihomo'),
                                 ('controller', config['panel_ip'], '/data')):
        services[name]['networks']['lan']['ipv4_address'] = address
        services[name]['volumes'] = [{'type': 'bind', 'source': folder.rstrip('/') + '/runtime', 'target': target}]
    network = compose['networks']['lan']
    network['driver_opts']['parent'] = parent
    network['ipam']['config'] = [{'subnet': config['subnet'], 'gateway': config['upstream']}]
    return yaml.safe_dump(compose, sort_keys=False, allow_unicode=True)


def save_installation(body):
    with LOCK:
        if existing_state():
            raise ValueError('already_installed')
        config, parent, warnings = validate_network(body)
        password = body.get('password', '')
        if not isinstance(password, str) or not 16 <= len(password) <= 256 or password != password.strip():
            raise ValueError('password_length')
        if password != body.get('confirm_password'):
            raise ValueError('password_mismatch')
        url = body.get('subscription', '')
        if not isinstance(url, str):
            raise ValueError('subscription')
        try:
            validate_url(url)
        except ValueError:
            raise ValueError('subscription') from None
        text = deployment_compose(config, parent)
        bootstrap(PROJECT, config, password, url, parent, deployment=text)
        return {'saved': True, 'panel_origin': config['panel_origin'], 'core_ip': config['core_ip'],
                'warnings': warnings, 'dhcp_enabled': False}


def allowed_hosts():
    addresses = ip_json('-4', 'address', 'show')
    return {a['local'] for entry in addresses for a in entry.get('addr_info', []) if a.get('family') == 'inet'} | {'127.0.0.1'}


class Handler(BaseHTTPRequestHandler):
    server_version = 'NASDeviceFlowSetup/0.1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass

    def send(self, status, data, content_type='application/json', extra=None):
        raw = json.dumps(data).encode() if content_type == 'application/json' else data.encode()
        self.send_response(status)
        for key, value in {'Content-Type': content_type + '; charset=utf-8', 'Content-Length': str(len(raw)),
                           'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                           'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer',
                           'Content-Security-Policy': "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'", **(extra or {})}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def trusted_host(self):
        try:
            host = urlsplit('http://' + self.headers.get('Host', ''))
            return host.hostname in self.server.allowed_ips and host.port == self.server.server_port
        except ValueError:
            return False

    def session(self):
        cookies = http.cookies.SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
            token = cookies['ndf-setup'].value
        except (KeyError, http.cookies.CookieError):
            return None
        with LOCK:
            session = SESSIONS.get(token)
            return session if session and session['expires'] > time.monotonic() else None

    def do_GET(self):
        if not self.trusted_host():
            return self.send(403, {'error': 'origin'})
        if self.path == '/':
            return self.send(200, HTML.read_text(), 'text/html')
        if self.path == '/health':
            return self.send(200, {'ok': True})
        session = self.session()
        if not session:
            return self.send(401, {'error': 'login'})
        try:
            if self.path == '/api/detect':
                return self.send(200, {**public_detection(), 'csrf': session['csrf']})
            if self.path == '/api/download':
                return self.send(200, (PROJECT / 'deployment.compose.yaml').read_text(), 'application/yaml',
                                 {'Content-Disposition': 'attachment; filename="deployment.compose.yaml"'})
        except (OSError, ValueError, subprocess.SubprocessError):
            return self.send(400, {'error': 'detect'})
        self.send(404, {'error': 'not_found'})

    def do_POST(self):
        expected_origin = 'http://' + self.headers.get('Host', '')
        if not self.trusted_host() or self.headers.get('Origin') != expected_origin:
            return self.send(403, {'error': 'origin'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send(415, {'error': 'request'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                return self.send(413, {'error': 'request'})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            return self.send(400, {'error': 'request'})
        if self.path == '/api/login':
            with LOCK:
                now = time.monotonic()
                # Bound sessions/failure buckets for a short-lived setup service.
                for key in list(SESSIONS):
                    if SESSIONS[key]['expires'] <= now:
                        del SESSIONS[key]
                for key in list(FAILURES):
                    if now - FAILURES[key][0] >= 60:
                        del FAILURES[key]
                key = self.client_address[0]
                first, count = FAILURES.get(key, (now, 0))
                if count >= 5 or len(FAILURES) > 1000 or len(SESSIONS) > 100:
                    return self.send(429, {'error': 'rate_limit'})
                submitted = body.get('code', '')
                if not isinstance(submitted, str) or not hmac.compare_digest(submitted.encode(), CODE.encode()):
                    FAILURES[key] = (first, count + 1)
                    return self.send(401, {'error': 'wrong_code'})
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                SESSIONS[token] = {'expires': now + 3600, 'csrf': csrf}
                FAILURES.pop(key, None)
                return self.send(200, {'csrf': csrf}, extra={'Set-Cookie': f'ndf-setup={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=3600'})
        session = self.session()
        if not session:
            return self.send(401, {'error': 'login'})
        if not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf']):
            return self.send(403, {'error': 'origin'})
        try:
            if self.path == '/api/check':
                config, parent, warnings = validate_network(body)
                return self.send(200, {'ok': True, 'config': config, 'warnings': warnings})
            if self.path == '/api/save':
                return self.send(200, save_installation(body))
        except ValueError as error:
            public_errors = {'network_changed', 'address_conflict', 'confirm_addresses', 'arp_unavailable',
                             'already_installed', 'password_length', 'password_mismatch', 'subscription', 'invalid_folder'}
            return self.send(400, {'error': str(error) if str(error) in public_errors else 'invalid_config'})
        except (OSError, TypeError, subprocess.SubprocessError):
            return self.send(400, {'error': 'save_failed'})
        self.send(404, {'error': 'not_found'})


def main():
    # Path is used as a bind source in the downloaded Compose file; reject interpolation.
    if not HOST_PROJECT.startswith('/') or any(c in HOST_PROJECT for c in ('\n', '\r', '\x00', '$')):
        raise SystemExit('Set NDF_PROJECT_PATH to the absolute NAS folder path.')
    PROJECT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    server.allowed_ips = allowed_hosts()
    server.daemon_threads = True
    server.socket.settimeout(30)
    print(f'NAS Device Flow setup / 安装向导: http://NAS-IP:{PORT}', flush=True)
    print(f'Setup access code / 安装访问码: {CODE}', flush=True)
    print('Open using the NAS IPv4 address. Stop this setup project after downloading deployment.compose.yaml.', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
