"""Installer boundaries: LAN discovery, no overwrites, private state and NAS GUI export."""
import importlib.util
import json
import fcntl
import os
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT / 'scripts')]
import install as wizard
import initialize as bootstrap
import setup_server as setup

ADDRESSES = [{'ifname': 'bond0', 'link_type': 'ether', 'flags': ['UP', 'LOWER_UP'],
              'linkinfo': {'info_kind': 'bond'}, 'addr_info': [
                  {'family': 'inet', 'scope': 'global', 'local': '192.168.50.10', 'prefixlen': 24}]}]
ROUTES = [{'dst': 'default', 'dev': 'bond0', 'gateway': '192.168.50.1'}]
LAN = wizard.usable_lans(ADDRESSES, ROUTES)[0]
BODY = {'parent': 'bond0', 'subnet': '192.168.50.0/24', 'nas_ip': '192.168.50.10',
        'upstream': '192.168.50.1', 'core_ip': '192.168.50.250', 'panel_ip': '192.168.50.254',
        'dhcp_start': '192.168.50.180', 'dhcp_end': '192.168.50.249', 'infrastructure': [],
        'fixed_nas': True, 'reserved_ips': True}


class DiscoveryTests(unittest.TestCase):
    def test_bond_parent_and_real_mask(self):
        self.assertEqual(LAN['parent'], 'bond0')
        self.assertEqual(LAN['upstream'], '192.168.50.1')
        addresses = json.loads(json.dumps(ADDRESSES))
        addresses[0]['addr_info'][0]['prefixlen'] = 23
        self.assertEqual(wizard.usable_lans(addresses, ROUTES)[0]['subnet'], '192.168.50.0/23')

    def test_virtual_tunnels_wifi_and_public_lans_are_excluded(self):
        for name, kind in [('docker0', 'bridge'), ('veth123', 'veth'), ('wg0', 'wireguard'), ('br-abcd', 'bridge')]:
            entry = dict(ADDRESSES[0], ifname=name, linkinfo={'info_kind': kind})
            self.assertEqual(wizard.usable_lans([entry], []), [])
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'wlan0/wireless').mkdir(parents=True)
            self.assertEqual(wizard.usable_lans([dict(ADDRESSES[0], ifname='wlan0')], [], Path(tmp)), [])
        for address in ('8.8.8.8', '169.254.1.2', '127.0.0.2'):
            entry = dict(ADDRESSES[0], addr_info=[dict(ADDRESSES[0]['addr_info'][0], local=address)])
            self.assertEqual(wizard.usable_lans([entry], []), [])

    def test_neighbor_and_nas_addresses_avoid_suggestions(self):
        known = wizard.occupied_addresses(ADDRESSES, [{'dst': '192.168.50.254', 'lladdr': '02:00:00:00:00:01'}])
        self.assertIn('192.168.50.10', known)
        self.assertNotIn('192.168.50.254', wizard.suggest_addresses(LAN['subnet'], known))
        first, last = wizard.suggest_pool(LAN['subnet'], {'192.168.50.200', '192.168.50.254'})
        self.assertFalse(int(wizard.ipaddress.ip_address(first)) <= int(wizard.ipaddress.ip_address('192.168.50.200')) <= int(wizard.ipaddress.ip_address(last)))

    def test_arp_conflict_and_inconclusive_checks(self):
        self.assertFalse(wizard.address_available('bond0', '192.168.50.10', {'192.168.50.10'}))
        for code, expected in ((0, True), (1, False), (2, None)):
            with patch.object(wizard.subprocess, 'run') as run:
                run.return_value.returncode = code
                self.assertIs(wizard.address_available('bond0', '192.168.50.250', set()), expected)
                self.assertIn('-D', run.call_args.args[0])

    def test_terminal_collect_invalid_selection_and_pool_retry(self):
        replies = iter(['bad', '1', '', 'y', '192.168.50.254', '192.168.50.253', 'y', '', '192.168.50.9', '192.168.50.11', '192.168.50.180', '192.168.50.249'])
        w = wizard.Wizard('en', ask=lambda _: next(replies), output=lambda _: None)
        config, parent = w.collect([LAN], {'192.168.50.10'}, probe=lambda *args: True)
        self.assertEqual(parent, 'bond0')
        self.assertFalse(config['dhcp_authoritative'])
        self.assertIn('192.168.50.10', config['infrastructure'])
        bootstrap.Settings(**config)


class CommitTests(unittest.TestCase):
    def test_concurrent_installer_lock_preserves_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(Path(tmp) / '.ndf-install.lock', 'w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    bootstrap.bootstrap(tmp, {}, 'fictional-panel-password', 'https://example.invalid/fixture.yaml', 'bond0')
                self.assertFalse((Path(tmp) / 'runtime').exists())
    def test_private_gui_state_is_transactional_and_dhcp_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            bootstrap.bootstrap(p, {}, 'fictional-panel-password', 'https://example.invalid/fixture.yaml', 'bond0', deployment='name: demo\n')
            self.assertFalse((p / 'runtime/control-center/dhcp.enabled').exists())
            self.assertEqual((p / 'deployment.compose.yaml').stat().st_mode & 0o777, 0o600)
            self.assertIn('PARENT_INTERFACE=bond0', (p / '.env').read_text())
            before = (p / 'runtime/config.yaml').read_bytes()
            with self.assertRaises(ValueError):
                bootstrap.bootstrap(p, {}, 'fictional-panel-password', 'https://example.invalid/other.yaml', 'eth0')
            self.assertEqual((p / 'runtime/config.yaml').read_bytes(), before)

    def test_staging_write_failure_leaves_no_partial_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            write = bootstrap.private_write
            def fail(path, value):
                if Path(path).name == 'deployment.compose.yaml':
                    raise OSError('fictional disk full')
                return write(path, value)
            with patch.object(bootstrap, 'private_write', side_effect=fail), self.assertRaises(OSError):
                bootstrap.bootstrap(tmp, {}, 'fictional-panel-password', 'https://example.invalid/fixture.yaml', 'bond0', deployment='name: demo')
            self.assertFalse((Path(tmp) / 'runtime').exists())
            self.assertFalse((Path(tmp) / '.env').exists())
            self.assertFalse(list(Path(tmp).glob('.ndf-install-*/')))

    def test_broken_symlink_and_invalid_parent_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / '.env').symlink_to(p / 'missing')
            with self.assertRaises(ValueError):
                bootstrap.bootstrap(p, {}, 'fictional-panel-password', 'https://example.invalid/fixture.yaml', 'eth0')
            self.assertTrue((p / '.env').is_symlink())
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            bootstrap.bootstrap(tmp, {}, 'fictional-panel-password', 'https://example.invalid/fixture.yaml', 'eth0\nBAD=1')


class NetworkValidationTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.object(setup, 'snapshot', return_value=(ADDRESSES, [LAN], {'192.168.50.10'}))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_detection_reports_host_facts_without_suggested_addresses(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, 'PROJECT', Path(folder)):
            result = setup.public_detection()
        self.assertEqual(result['lans'][0]['nas_ip'], LAN['nas_ip'])
        self.assertEqual(result['lans'][0]['upstream'], LAN['upstream'])
        for key in ('core_hint', 'panel_hint', 'dhcp_start', 'dhcp_end'):
            self.assertNotIn(key, result['lans'][0])

    def test_conflict_requires_new_address_and_probe_error_requires_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'address_conflict'):
            setup.validate_network(BODY, probe=lambda *args: False)
        with self.assertRaisesRegex(ValueError, 'arp_unavailable'):
            setup.validate_network(BODY, probe=lambda *args: None)
        config, _, warnings = setup.validate_network(dict(BODY, manual_ip_check=True), probe=lambda *args: None)
        self.assertIn('arp_unavailable', warnings)
        self.assertEqual(config['infrastructure'], ['192.168.50.10'])

    def test_tampered_interface_and_reserved_pool_rejected(self):
        for changes in ({'parent': 'eth99'}, {'subnet': '192.168.60.0/24'}, {'nas_ip': '192.168.50.99'},
                        {'fixed_nas': False}, {'reserved_ips': 'true'}, {'dhcp_start': '192.168.50.5'}, {'core_ip': []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                setup.validate_network(dict(BODY, **changes), probe=lambda *args: True)

    def test_nas_alias_is_excluded_from_pool(self):
        addresses = json.loads(json.dumps(ADDRESSES))
        addresses[0]['addr_info'].append(dict(addresses[0]['addr_info'][0], local='192.168.50.200'))
        with patch.object(setup, 'snapshot', return_value=(addresses, [LAN], {'192.168.50.10', '192.168.50.200'})):
            with self.assertRaises(ValueError):
                setup.validate_network(BODY, probe=lambda *args: True)

    def test_gui_export_has_no_env_dependencies_or_credentials(self):
        config, parent, _ = setup.validate_network(BODY, probe=lambda *args: True)
        text = setup.deployment_compose(config, parent, ROOT / 'compose.yaml', '/volume1/docker/fictional project')
        result = setup.yaml.safe_load(text)
        self.assertNotIn('${', text)
        self.assertNotIn('build', result['services']['controller'])
        self.assertEqual(result['services']['controller']['volumes'][0]['source'], '/volume1/docker/fictional project/runtime')
        self.assertEqual(result['networks']['lan']['driver_opts']['parent'], 'bond0')
        self.assertEqual(result['services']['mihomo']['networks']['lan']['ipv4_address'], BODY['core_ip'])
        for service in result['services'].values():
            self.assertIn('DAC_OVERRIDE', service['cap_add'])
            self.assertNotIn('/var/run/docker.sock', str(service))
        for folder in ('relative/path', '/volume1/${BAD}', '/volume1/\nBAD'):
            with self.assertRaises(ValueError):
                setup.deployment_compose(config, parent, ROOT / 'compose.yaml', folder)


class SetupHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in [('PROJECT', Path(self.tmp.name)), ('HOST_PROJECT', '/volume1/docker/fictional-install'),
                            ('TEMPLATE', ROOT / 'compose.yaml'), ('CODE', 'fictional-setup-access-code'), ('SESSIONS', {}), ('FAILURES', {})]:
            p = patch.object(setup, name, value)
            p.start(); self.addCleanup(p.stop)
        p = patch.object(setup, 'snapshot', return_value=(ADDRESSES, [dict(LAN)], {'192.168.50.10'}))
        p.start(); self.addCleanup(p.stop)
        # Default callback is captured by validate_network; pass through a patched wrapper.
        validate = setup.validate_network
        p = patch.object(setup, 'validate_network', side_effect=lambda body: validate(body, probe=lambda *args: True))
        p.start(); self.addCleanup(p.stop)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), setup.Handler)
        self.http.allowed_ips = {'127.0.0.1'}
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)

    def request(self, path, body=None, headers=None):
        h = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{self.http.server_port}'}
        h.update(headers or {})
        conn = HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        conn.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), h)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def auth(self):
        status, headers, body = self.request('/api/login', {'code': 'fictional-setup-access-code'})
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        return {'Cookie': headers['Set-Cookie'], 'X-CSRF-Token': json.loads(body)['csrf']}

    def test_login_origin_host_and_csrf_boundaries(self):
        self.assertEqual(self.request('/api/detect')[0], 401)
        self.assertEqual(self.request('/api/download')[0], 401)
        self.assertEqual(self.request('/api/login', {'code': 'fictional-setup-access-code'}, {'Origin': 'http://example.invalid'})[0], 403)
        self.assertEqual(self.request('/', headers={'Host': 'example.invalid:9088'})[0], 403)
        self.assertEqual(self.request('/', headers={'Host': '[bad'})[0], 403)
        auth = self.auth()
        self.assertEqual(self.request('/api/check', BODY, {'Cookie': auth['Cookie']})[0], 403)
        self.assertEqual(self.request('/api/check', BODY, auth)[0], 200)

    def test_failed_password_and_validation_leave_no_runtime(self):
        auth = self.auth()
        body = dict(BODY, password='short', confirm_password='short', subscription='https://example.invalid/fixture.yaml')
        self.assertEqual(self.request('/api/save', body, auth)[0], 400)
        self.assertFalse((setup.PROJECT / 'runtime').exists())

    def test_save_download_restart_and_no_overwrite(self):
        auth = self.auth()
        body = dict(BODY, password='fictional-panel-password', confirm_password='fictional-panel-password', subscription='https://example.invalid/fixture.yaml')
        status, _, result = self.request('/api/save', body, auth)
        self.assertEqual(status, 200, result)
        self.assertFalse(json.loads(result)['dhcp_enabled'])
        self.assertFalse((setup.PROJECT / 'runtime/control-center/dhcp.enabled').exists())
        status, _, exported = self.request('/api/download', headers=auth)
        self.assertEqual(status, 200)
        self.assertNotIn(b'fictional-panel-password', exported)
        self.assertNotIn(b'example.invalid', exported)
        self.assertEqual(self.request('/api/save', body, auth)[0], 400)
        status, _, state = self.request('/api/detect', headers=auth)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(state)['installed'])
        self.assertNotIn(b'fictional-panel-password', state)

    def test_failed_access_codes_rate_limited_and_not_in_page(self):
        self.assertNotIn(b'fictional-setup-access-code', self.request('/')[2])
        for _ in range(5):
            self.assertEqual(self.request('/api/login', {'code': 'wrong'})[0], 401)
        self.assertEqual(self.request('/api/login', {'code': 'fictional-setup-access-code'})[0], 429)


if __name__ == '__main__':
    unittest.main()
