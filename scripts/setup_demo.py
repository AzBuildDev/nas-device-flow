#!/usr/bin/env python3
"""Fictional browser installer demo. Loopback only; no LAN probes or Docker calls."""
import argparse
import json
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT / 'scripts')]
import setup_server as setup
from install import usable_lans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=9087)
args = parser.parse_args()
addresses = [{'ifname': 'bond0', 'link_type': 'ether', 'flags': ['UP'], 'addr_info': [
    {'family': 'inet', 'scope': 'global', 'local': '192.168.50.10', 'prefixlen': 24}]}]
lans = usable_lans(addresses, [{'dev': 'bond0', 'dst': 'default', 'gateway': '192.168.50.1'}])
with tempfile.TemporaryDirectory(prefix='ndf-fictional-setup-') as tmp:
    folder = Path(tmp)
    html = folder / 'demo.html'
    html.write_text((ROOT / 'app/setup.html').read_text().replace('<main>', '<main><p class="notice">Fictional demo / 虚构安装演示 · 不连接真实网络 · 配置在退出时删除</p>'))
    setup.PROJECT = folder / 'project'
    setup.PROJECT.mkdir()
    setup.HOST_PROJECT = '/volume1/docker/fictional-demo'
    setup.HTML = html
    setup.TEMPLATE = ROOT / 'compose.yaml'
    setup.CODE = 'demo-setup-access-code'
    validation = setup.validate_network
    with patch.object(setup, 'snapshot', side_effect=lambda: (addresses, json.loads(json.dumps(lans)), {'192.168.50.10'})), \
         patch.object(setup, 'validate_network', side_effect=lambda body: validation(body, probe=lambda *args: True)):
        server = ThreadingHTTPServer(('127.0.0.1', args.port), setup.Handler)
        server.allowed_ips = {'127.0.0.1'}
        print(f'Fictional setup: http://127.0.0.1:{args.port} · code: demo-setup-access-code', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
