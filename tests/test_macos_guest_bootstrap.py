"""Validate guest network guards without installing software or changing routes."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/macos/guest-bootstrap.sh'
NETWORK_CHECK = SCRIPT.read_text().split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]


class GuestNetworkGuards(unittest.TestCase):
    def run_check(self, interface=None, routes=None):
        if interface is None:
            interface = [{'ifname': 'ndflan', 'link_type': 'ether', 'flags': ['UP'],
                          'addr_info': [{'family': 'inet', 'scope': 'global',
                                         'local': '192.168.50.20', 'prefixlen': 24}]}]
        if routes is None:
            routes = [{'dev': 'ndflan', 'gateway': '192.168.50.1'}]
        def output(args, **kwargs):
            return json.dumps(interface if 'address' in args else routes).encode()
        try:
            with patch('sys.argv', ['check', 'ndflan']), patch('subprocess.check_output', side_effect=output), contextlib.redirect_stderr(io.StringIO()):
                exec(compile(NETWORK_CHECK, str(SCRIPT), 'exec'), {})
            return 0
        except SystemExit as exc:
            return exc.code

    def test_bridged_private_lan_is_accepted(self):
        self.assertEqual(self.run_check(), 0)

    def test_nat_default_is_rejected(self):
        self.assertEqual(self.run_check(routes=[{'dev': 'lima0', 'gateway': '192.168.5.2'}]), 1)

    def test_second_default_is_rejected(self):
        self.assertEqual(self.run_check(routes=[{'dev': 'ndflan', 'gateway': '192.168.50.1'}, {'dev': 'lima0', 'gateway': '192.168.5.2'}]), 1)

    def test_missing_interface_is_rejected(self):
        self.assertEqual(self.run_check(interface=[]), 1)

    def test_public_or_link_local_address_is_rejected(self):
        for address in ('203.0.113.20', '169.254.1.20'):
            interface = [{'link_type': 'ether', 'flags': ['UP'], 'addr_info': [{'family': 'inet', 'scope': 'global', 'local': address, 'prefixlen': 24}]}]
            self.assertEqual(self.run_check(interface=interface), 1)

    def test_off_subnet_gateway_is_rejected(self):
        self.assertEqual(self.run_check(routes=[{'dev': 'ndflan', 'gateway': '10.20.30.1'}]), 1)

    def test_interface_down_is_rejected(self):
        self.assertEqual(self.run_check(interface=[{'link_type': 'ether', 'flags': [], 'addr_info': []}]), 1)
