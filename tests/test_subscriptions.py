import tempfile,unittest,json
from pathlib import Path
import yaml
from subscriptions import Subscriptions,validate_url
class SubscriptionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.root.joinpath('base.yaml').write_text(yaml.safe_dump({'proxy-providers':{'subscription':{'url':'https://example.com/private-token','path':'old.yaml'}},'rules':['MATCH,DIRECT']}))
  self.r=Subscriptions(self.root,lambda p,s:p.write_text(s))
 def tearDown(self):self.tmp.cleanup()
 def test_summary_private(self):
  result=self.r.summaries();self.assertNotIn('private-token',json.dumps(result));self.assertEqual(result['active'],'original')
 def test_switch_preserves_rules(self):
  self.r.add('新订阅','https://new.example/test');v=self.r.load();identifier=v['items'][1]['id'];calls=[]
  self.r.switch(identifier,lambda:calls.append(1));b=yaml.safe_load((self.root/'base.yaml').read_text());self.assertEqual(b['rules'],['MATCH,DIRECT']);self.assertEqual(self.r.load()['active'],identifier);self.assertIn('sub-',b['proxy-providers']['subscription']['path'])
 def test_failed_switch_rolls_back(self):
  self.r.add('坏订阅','https://bad.example/test');old=(self.root/'base.yaml').read_text();count=[]
  def apply():
   count.append(1)
   if len(count)==1:raise RuntimeError('do not expose secret')
  with self.assertRaisesRegex(RuntimeError,'已恢复'):self.r.switch(self.r.load()['items'][1]['id'],apply)
  self.assertEqual((self.root/'base.yaml').read_text(),old);self.assertEqual(self.r.load()['active'],'original');self.assertEqual(len(count),2)
 def test_active_not_deleted(self):
  with self.assertRaises(ValueError):self.r.remove('original')
 def test_duplicate_and_url(self):
  self.r.load()
  with self.assertRaises(ValueError):self.r.add('重复','https://example.com/private-token')
  for url in ('file:///secret','https://user:pass@example.com','https://example.com/#secret'):
   with self.assertRaises(ValueError):validate_url(url)
