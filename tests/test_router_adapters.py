import tempfile, unittest
from pathlib import Path
from unittest.mock import Mock
from router_adapters import OpenWrtClient,RouterOSClient,endpoint,create_client
class AdaptersTests(unittest.TestCase):
 def test_openwrt(self):
  c=OpenWrtClient('http://192.168.1.1','reader','test');c.request=Mock(side_effect=[{'result':[0,{'ubus_rpc_session':'token'}]},{'result':[0,{'data':'123 aa:bb:cc:dd:ee:ff 192.168.1.2 laptop *\nbad'}]}])
  d=c.devices()['aa:bb:cc:dd:ee:ff'];self.assertEqual(d['router_name'],'laptop');self.assertNotIn('ip',d)
  self.assertEqual(c.request.call_args_list[1].args[1]['params'][2],'read')
 def test_rpc_denied(self):
  c=OpenWrtClient('http://192.168.1.1','reader','test');c.request=Mock(return_value={'result':[6]})
  with self.assertRaises(RuntimeError): c.devices()
 def test_routeros_get(self):
  c=RouterOSClient('https://router.local','reader','test');c.request=Mock(return_value=[{'mac-address':'AA:BB:CC:DD:EE:FF','host-name':'phone','address':'1.2.3.4'}])
  d=c.devices()['aa:bb:cc:dd:ee:ff'];self.assertEqual(d['router_name'],'phone');self.assertNotIn('enabled',d);self.assertNotIn('ip',d)
  self.assertEqual(c.request.call_args.args,('/rest/ip/dhcp-server/lease',))
 def test_url_validation(self):
  for url in ('file:///etc/passwd','http://user:password@router','http://router/other','http://router?secret=x'):
   with self.assertRaises(ValueError):endpoint(url)
 def test_disabled(self):
  with tempfile.TemporaryDirectory() as d:
   Path(d,'router-adapter.json').write_text('{"type":"none"}')
   self.assertIsNone(create_client(d))
 def test_placeholders(self):
  self.assertEqual(OpenWrtClient.parse('123 aa:bb:cc:dd:ee:ff 1.2.3.4 * *')['aa:bb:cc:dd:ee:ff']['router_name'],'')
  self.assertEqual(RouterOSClient.parse([{'mac-address':'bad'}]),{})
