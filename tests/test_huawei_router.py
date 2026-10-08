import unittest
from huawei_router import normalize

class RouterNamesTests(unittest.TestCase):
    def test_names_and_brand(self):
        r=normalize([{'MACAddress':'AA:BB:CC:DD:EE:FF','HostName':'海信VIDAA电视','DevBrands':'Hisense','IconType':'television','IPAddress':'192.168.50.9'}])
        d=r['aa:bb:cc:dd:ee:ff']
        self.assertEqual(d['router_name'],'海信VIDAA电视')
        self.assertEqual(d['router_brand'],'Hisense')
        self.assertNotIn('ip',d)
        self.assertNotIn('enabled',d)
        self.assertNotIn('name',d)
    def test_alias_and_unknown(self):
        d=normalize([{'MACAddress':'aa:bb:cc:dd:ee:ff','ActualName':'客厅电视','HostName':'android','ActualManu':'Default','DevBrands':'Hisense'}])['aa:bb:cc:dd:ee:ff']
        self.assertEqual(d['router_name'],'客厅电视')
        self.assertEqual(d['router_brand'],'Hisense')
        self.assertEqual(d['router_model'],'')
    def test_invalid_and_placeholder(self):
        self.assertEqual(normalize([{'MACAddress':'bad'}]),{})
        self.assertEqual(normalize([{'MACAddress':'aa:bb:cc:dd:ee:ff','HostName':'未知设备-EEFF'}])['aa:bb:cc:dd:ee:ff']['router_name'],'')

    def test_duplicate_history_preserves_name(self):
        d=normalize([{'MACAddress':'aa:bb:cc:dd:ee:ff','HostName':'MacBook'}, {'MACAddress':'aa:bb:cc:dd:ee:ff','HostName':'未知设备-EEFF'}])
        self.assertEqual(d['aa:bb:cc:dd:ee:ff']['router_name'],'MacBook')
