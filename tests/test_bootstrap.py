import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from settings import Settings
spec=importlib.util.spec_from_file_location('initialize',ROOT/'scripts/initialize.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
class BootstrapTests(unittest.TestCase):
 def test_private_state_default_direct_and_no_dhcp(self):
  with tempfile.TemporaryDirectory() as t:
   b.initialize(t,{},'fictional-panel-password','https://example.invalid/fictional.yaml')
   r=Path(t)/'runtime';d=r/'control-center';cfg=b.yaml.safe_load((r/'config.yaml').read_text())
   self.assertEqual(cfg['rules'],['MATCH,DIRECT']);self.assertFalse((d/'dhcp.enabled').exists())
   self.assertNotEqual((r/'secret').read_text(),(d/'admin-secret').read_text())
   self.assertEqual((r/'secret').stat().st_mode&0o777,0o600)
   self.assertEqual(json.loads((d/'devices.json').read_text()),{})
   with self.assertRaises(ValueError):b.initialize(t,{},'fictional-panel-password','https://example.invalid/fictional.yaml')
 def test_infrastructure_pool_rejected(self):
  with self.assertRaises(ValueError):Settings(infrastructure=['192.168.50.200'])
 def test_invalid_fixed_host_rejected_before_state_creation(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):b.initialize(t,{},'fictional-panel-password','https://example.invalid/demo','bad\n')
   self.assertFalse((Path(t)/'runtime').exists())
 def test_subnet_is_configurable(self):
  s=Settings(subnet='192.168.60.0/24',upstream='192.168.60.1',core_ip='192.168.60.250',panel_ip='192.168.60.254',dhcp_start='192.168.60.180',dhcp_end='192.168.60.249')
  self.assertTrue(s.valid_ip('192.168.60.180'));self.assertFalse(s.valid_ip('192.168.50.180'));self.assertIn('192.168.60.250',s.dnsmasq('/data/control-center'))
 def test_invalid_network_and_origin(self):
  for kwargs in ({'subnet':'8.8.8.0/24'},{'core_ip':'192.168.50.1'},{'panel_origin':'http://user:pass@example.invalid/'}):
   with self.assertRaises(ValueError):Settings(**kwargs)
if __name__=='__main__':unittest.main()
