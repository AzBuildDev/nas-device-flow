import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
import unittest
from access_status import AccessStatus, valid_leases


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.device = {'mac': 'aa:bb:cc:dd:ee:ff', 'ip': '192.168.50.174', 'enabled': True, 'online': True}
        self.status = AccessStatus()

    def test_enabled_and_online_do_not_prove_gateway(self):
        self.assertFalse(self.status.status(self.device, set(), now=100)['gateway_observed'])

    def test_lease_is_configuration_not_gateway_evidence(self):
        leases = valid_leases('200 AA:BB:CC:DD:EE:FF 192.168.50.174 ipad *', now=100)
        result = self.status.status(self.device, leases, now=100)
        self.assertTrue(result['dhcp_assigned'])
        self.assertFalse(result['gateway_observed'])

    def test_expired_and_different_ip_leases_are_not_assigned(self):
        leases = valid_leases('99 aa:bb:cc:dd:ee:ff 192.168.50.174 ipad *\n0 aa:bb:cc:dd:ee:ff 192.168.50.175 ipad *\nbad lease', now=100)
        self.assertFalse(self.status.status(self.device, leases, now=100)['dhcp_assigned'])

    def test_observed_connections_expire_and_do_not_follow_ip_moves(self):
        self.status.sample([{'metadata': {'sourceIP': '192.168.50.174'}}], {'192.168.50.174': self.device['mac']}, now=100)
        self.assertTrue(self.status.status(self.device, set(), now=101)['gateway_observed'])
        self.assertFalse(self.status.status(self.device, set(), now=281)['gateway_observed'])
        moved = dict(self.device, ip='192.168.50.175')
        self.assertFalse(self.status.status(moved, set(), now=101)['gateway_observed'])

    def test_new_mac_cannot_inherit_connection_or_lease_evidence(self):
        self.status.sample([{'metadata': {'sourceIP': self.device['ip']}}], {self.device['ip']: self.device['mac']}, now=100)
        new_device = dict(self.device, mac='02:00:00:00:00:01')
        leases = {(self.device['mac'], self.device['ip'])}
        result = self.status.status(new_device, leases, now=101)
        self.assertFalse(result['dhcp_assigned'])
        self.assertFalse(result['gateway_observed'])

    def test_unowned_sources_do_not_confirm_devices(self):
        self.status.sample([{'metadata': {'sourceIP': '192.168.50.174'}}], {}, now=100)
        self.assertFalse(self.status.status(self.device, set(), now=101)['gateway_observed'])


if __name__ == '__main__':
    unittest.main()
