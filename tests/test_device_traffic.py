import json,tempfile,time,unittest
from pathlib import Path
from device_traffic import DeviceTraffic,ip_owners,proxy_nodes
MAC='aa:bb:cc:dd:ee:ff';OTHER='11:22:33:44:55:66'
def conn(key='a',up=10,down=20,node='node',ip='192.168.50.175'):
 return {'id':key,'upload':up,'download':down,'chains':[node,'PROXY'],'metadata':{'sourceIP':ip,'host':'private.example'}}
class DeviceTrafficTests(unittest.TestCase):
 def setUp(self):self.t=DeviceTraffic();self.owners={'192.168.50.175':MAC};self.nodes={'node'}
 def sample(self,rows):self.t.sample(rows,self.owners,self.nodes)
 def totals(self):return self.t.snapshot()['devices'].get(MAC,{'total':0})
 def test_baseline_and_delta(self):
  self.sample([conn(up=100,down=200)]);self.assertEqual(self.totals()['total'],0)
  self.sample([conn(up=130,down=240)]);self.assertEqual(self.totals()['total'],70)
  self.sample([conn(up=130,down=240)]);self.assertEqual(self.totals()['total'],70)
 def test_closed_connections_remain(self):
  self.sample([]);self.sample([conn()]);self.sample([]);self.assertEqual(self.totals()['total'],30);self.assertEqual(self.t.active,{})
 def test_direct_and_unknown_excluded(self):
  self.sample([]);self.sample([conn(node='DIRECT'),conn(key='b',node='REJECT'),conn(key='c',ip='192.168.50.99')]);self.assertEqual(self.totals()['total'],0)
 def test_counter_reset_no_negative(self):
  self.sample([]);self.sample([conn(up=100,down=200)]);self.sample([conn(up=5,down=10)]);self.assertEqual(self.totals()['total'],300)
  self.sample([conn(up=6,down=12)]);self.assertEqual(self.totals()['total'],303)
 def test_owner_is_fixed_for_connection(self):
  self.sample([conn()]);self.owners['192.168.50.175']=OTHER;self.sample([conn(up=15,down=25)])
  self.assertEqual(self.totals()['total'],10);self.assertNotIn(OTHER,self.t.snapshot()['devices'])
 def test_mac_same_despite_new_ip(self):
  self.sample([]);self.sample([conn()]);self.owners={'192.168.50.176':MAC};self.sample([conn(key='b',ip='192.168.50.176')]);self.assertEqual(self.totals()['total'],60)
 def test_persistence_and_restart_dedup(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'stats.json';writer=lambda p,s:p.write_text(s)
   t=DeviceTraffic(path,writer);t.sample([],self.owners,self.nodes);t.sample([conn()],self.owners,self.nodes);t.flush()
   restored=DeviceTraffic(path,writer);restored.sample([conn(up=15,down=25)],self.owners,self.nodes)
   self.assertEqual(restored.snapshot()['devices'][MAC]['total'],40)
   self.assertNotIn('private.example',path.read_text())
 def test_invalid_record_preserved(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'stats.json';path.write_text('broken');t=DeviceTraffic(path,lambda p,s:p.write_text(s));t.sample([],{},set());t.flush();self.assertEqual(path.read_text(),'broken');self.assertFalse(t.snapshot()['ok'])
 def test_proxy_types_and_ambiguous_ip(self):
  self.assertEqual(proxy_nodes({'node':{'type':'Trojan'},'DIRECT':{'type':'Direct'},'group':{'type':'Selector'}}),{'node'})
  self.assertEqual(ip_owners({MAC:{'ip':'1.2.3.4'},OTHER:{'ip':'1.2.3.4'}}),{})

 def test_provider_nodes_not_in_proxies(self):
  self.assertEqual(proxy_nodes({'PROXY':{'type':'Selector'}},{'subscription':{'proxies':[{'name':'provider-node','type':'Trojan'},{'name':'direct-node','type':'Direct'}]}}),{'provider-node'})
