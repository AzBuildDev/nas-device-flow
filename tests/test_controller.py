import importlib.util,unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'app'))
spec=importlib.util.spec_from_file_location('controller',Path(__file__).parents[1]/'app'/'server.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class PolicyTests(unittest.TestCase):
 def setUp(self):
  self.settings_patch=patch.object(c,'SETTINGS',c.Settings(subnet='192.168.50.0/24',infrastructure=['192.168.50.10']));self.settings_patch.start();self.addCleanup(self.settings_patch.stop)
  self.base={'rules':['RULE-SET,cn-domain,DIRECT','MATCH,PROXY'],'dns':{'nameserver':['old']}}
 def test_unknown_devices_default_direct(self):
  r=c.render(self.base,{});self.assertEqual(r['rules'],['MATCH,DIRECT'])
 def test_only_enabled_devices_enter_smart_rules(self):
  ds={'a':{'ip':'192.168.50.175','enabled':True},'b':{'ip':'192.168.50.174','enabled':False}}
  r=c.render(self.base,ds);self.assertEqual(r['rules'],['SUB-RULE,(SRC-IP-CIDR,192.168.50.175/32),smart-routing','MATCH,DIRECT']);self.assertEqual(r['sub-rules']['smart-routing'],self.base['rules'])
 def test_outside_subnet_and_infrastructure_never_enabled(self):
  r=c.render(self.base,{str(i):{'ip':ip,'enabled':True} for i,ip in enumerate(['8.8.8.8','192.168.50.10','192.168.50.250','192.168.50.1','192.168.50.255'])});self.assertEqual(r['rules'],['MATCH,DIRECT'])
 def test_ip_reuse_revokes_old_enabled_device(self):
  ds={'00:11:22:33:44:55':{'ip':'192.168.50.175','enabled':True}}
  c.update_device(ds,'aa:bb:cc:dd:ee:ff','192.168.50.175');self.assertEqual(ds['00:11:22:33:44:55']['ip'],'');self.assertFalse(ds['aa:bb:cc:dd:ee:ff']['enabled']);self.assertEqual(c.render(self.base,ds)['rules'],['MATCH,DIRECT'])
 def test_mac_moving_ip_retains_preference(self):
  ds={'00:11:22:33:44:55':{'ip':'192.168.50.175','enabled':True}}
  c.update_device(ds,'00:11:22:33:44:55','192.168.50.200');self.assertTrue(ds['00:11:22:33:44:55']['enabled']);self.assertIn('192.168.50.200',c.render(self.base,ds)['rules'][0])
 def test_reload_failure_restores_config(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=root/'control-center';data.mkdir();(root/'config.yaml').write_text('original');(data/'base.yaml').write_text(c.yaml.safe_dump(self.base))
   with patch.object(c,'ROOT',root),patch.object(c,'DATA',data),patch.object(c,'core',side_effect=RuntimeError('failed')):
    with self.assertRaises(RuntimeError):c.apply({},True)
   self.assertEqual((root/'config.yaml').read_text(),'original')
 def test_enabled_address_is_reserved_against_reuse(self):
  with tempfile.TemporaryDirectory() as t:
   data=Path(t);(data/'fixed.hosts').write_text('00:aa:bb:cc:dd:ee,set:infrastructure,192.168.50.10,infinite\n')
   with patch.object(c,'DATA',data):
    c.reserve_enabled({'00:11:22:33:44:55':{'enabled':True,'ip':'192.168.50.200'},'aa:bb:cc:dd:ee:ff':{'enabled':False,'ip':'192.168.50.201'}})
   hosts=(data/'dhcp.hosts').read_text();self.assertIn('00:11:22:33:44:55,192.168.50.200,12h',hosts);self.assertNotIn('192.168.50.201',hosts);self.assertIn('infrastructure',hosts)
 def test_dns_is_direct_for_all_clients(self):
  self.assertTrue(all('#PROXY' not in x for x in c.render(self.base,{})['dns']['nameserver']))
if __name__=='__main__':unittest.main()
