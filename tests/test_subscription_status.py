import sys,time,unittest,copy
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from subscription_status import provider_status

class StatusTests(unittest.TestCase):
 def setUp(self):
  self.now=1800000000
  self.node={'name':'fictional','type':'Vless','alive':True,'history':[{'time':datetime.fromtimestamp(self.now-5,timezone.utc).isoformat(),'delay':123}]}
  self.provider={'proxies':[self.node],'testUrl':'https://example.invalid/test','subscriptionInfo':{'Upload':100,'Download':200,'Total':1000,'Expire':self.now+1000}}
 def status(self,selected='fictional',provider=None):return provider_status(self.provider if provider is None else provider,selected,self.now)
 def test_recent_selected_health_and_account(self):
  s=self.status();self.assertEqual(s['state'],'healthy');self.assertEqual(s['delay_ms'],123);self.assertEqual(s['checked_at'],self.now-5);self.assertEqual(s['remaining'],700);self.assertEqual(s['account'],'normal')
 def test_no_nodes_and_core_unavailable(self):
  self.assertEqual(provider_status(None,'')['state'],'unavailable')
  self.assertEqual(self.status(provider={'proxies':[]})['state'],'unloaded')
  self.assertEqual(self.status(provider={'proxies':None})['state'],'unloaded')
 def test_loaded_without_history_is_not_healthy(self):
  self.node['history']=[];self.assertEqual(self.status()['state'],'untested')
 def test_failed_delay_and_alive(self):
  self.node['history'][0]['delay']=0;self.assertEqual(self.status()['state'],'failed')
  self.node['history'][0]['delay']=123;self.node['alive']=False;self.assertEqual(self.status()['state'],'failed')
 def test_stale_record_and_invalid_future(self):
  self.node['history'][0]['time']=datetime.fromtimestamp(self.now-601,timezone.utc).isoformat();self.assertEqual(self.status()['state'],'stale');self.assertIsNone(self.status()['delay_ms'])
  self.node['history'][0]['time']=datetime.fromtimestamp(self.now+1000,timezone.utc).isoformat();self.assertEqual(self.status()['state'],'untested')
 def test_bad_history_never_reports_success(self):
  for history in ([{'time':'invalid','delay':123}],['malformed'],[{'time':self.node['history'][0]['time'],'delay':float('nan')}],{'bad':1}):
   with self.subTest(history=history):
    self.node['history']=history;self.assertEqual(self.status()['state'],'untested')
 def test_direct_and_missing_selection(self):
  self.assertEqual(self.status('DIRECT')['state'],'direct')
  self.assertEqual(self.status('REJECT')['state'],'direct')
  self.assertEqual(self.status('missing')['state'],'not_selected')
  self.node['type']='Direct';self.assertEqual(self.status()['state'],'direct')
 def test_selected_failed_not_masked_by_other_healthy_node(self):
  bad=copy.deepcopy(self.node);bad['name']='bad';bad['history'][0]['delay']=0;self.provider['proxies'].append(bad)
  s=self.status('bad');self.assertEqual(s['state'],'failed');self.assertEqual(s['healthy_count'],1);self.assertEqual(s['tested_count'],2)
 def test_uses_provider_test_url_history(self):
  self.node['extra']={self.provider['testUrl']:{'alive':False,'history':[dict(self.node['history'][0],delay=0)]}}
  self.assertEqual(self.status()['state'],'failed')
 def test_expired_and_exhausted_are_separate_from_health(self):
  self.provider['subscriptionInfo']['Expire']=self.now;self.assertEqual(self.status()['account'],'expired');self.assertEqual(self.status()['state'],'healthy')
  self.provider['subscriptionInfo']['Expire']=self.now+100;self.provider['subscriptionInfo']['Download']=2000;self.assertEqual(self.status()['account'],'exhausted');self.assertEqual(self.status()['remaining'],0)
 def test_unknown_metadata_not_expired_or_exhausted(self):
  for metadata in ({},{'Total':0,'Expire':0},{'Total':True,'Upload':0,'Download':0},{'Total':1000,'Upload':0}):
   self.provider['subscriptionInfo']=metadata;self.assertEqual(self.status()['account'],'unknown');self.assertIsNone(self.status()['remaining'])
 def test_does_not_expose_credentials_or_mutate_provider(self):
  self.provider.update(url='https://example.invalid/private-token',secret='fictional-secret');old=copy.deepcopy(self.provider)
  result=self.status();self.assertNotIn('private-token',str(result));self.assertNotIn('fictional-secret',str(result));self.assertEqual(old,self.provider)
