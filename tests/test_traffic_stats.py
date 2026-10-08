import time,unittest
from traffic_stats import TrafficStats
class StatsTests(unittest.TestCase):
 def test_values_and_privacy(self):
  s=TrafficStats();s.update({'up':10,'down':20},{'uploadTotal':100,'downloadTotal':200,'memory':30,'connections':[{'metadata':{'host':'private.example'}}]})
  d=s.snapshot();self.assertTrue(d['ok']);self.assertEqual(d['connections'],1);self.assertEqual(d['download_total'],200);self.assertNotIn('private.example',str(d))
 def test_bounded_and_reset(self):
  s=TrafficStats()
  for i in range(200):s.update({'up':-1,'down':i},{'uploadTotal':i,'downloadTotal':i})
  self.assertEqual(len(s.snapshot()['history']),180);self.assertEqual(s.snapshot()['up'],0)
  s.update({}, {'uploadTotal':0,'downloadTotal':0});self.assertEqual(s.snapshot()['upload_total'],0)
 def test_failure_and_stale(self):
  s=TrafficStats();s.update({'up':20},now=time.time()-10);self.assertFalse(s.snapshot()['ok']);s.update({'up':2});s.failed();self.assertFalse(s.snapshot()['ok'])
