import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import server as c
from preferences import load_preferences,save_preferences

class PreferenceTests(unittest.TestCase):
 def test_future_devices_only_and_preferences_survive_reload(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)
   with patch.object(c,'DATA',data):
    devices={};c.update_device(devices,'02:00:00:00:00:01','192.168.50.101')
    self.assertFalse(devices['02:00:00:00:00:01']['enabled'])
    save_preferences(data,{'new_device_proxy':True},c.atomic)
    self.assertTrue(load_preferences(data)['new_device_proxy'])
    c.update_device(devices,'02:00:00:00:00:01','192.168.50.102')
    self.assertFalse(devices['02:00:00:00:00:01']['enabled'])
    c.update_device(devices,'02:00:00:00:00:02','192.168.50.103')
    self.assertTrue(devices['02:00:00:00:00:02']['enabled'])
    self.assertEqual((data/'preferences.json').stat().st_mode & 0o777,0o600)
 def test_invalid_preferences_do_not_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp);save_preferences(data,{'new_device_proxy':False},c.atomic)
   for value in ({'new_device_proxy':'false'},{'new_device_proxy':1},{'new_device_proxy':True,'subnet':'anything'},{}):
    with self.assertRaises(ValueError):save_preferences(data,value,c.atomic)
   self.assertFalse(load_preferences(data)['new_device_proxy'])

 def test_upgrade_without_preferences_preserves_enabled_and_disabled_devices(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)
   devices={'02:00:00:00:00:01':{'mac':'02:00:00:00:00:01','ip':'192.168.50.101','enabled':True},'02:00:00:00:00:02':{'mac':'02:00:00:00:00:02','ip':'192.168.50.102','enabled':False}}
   with patch.object(c,'DATA',data):
    c.save(devices);restored=c.load()
    self.assertFalse(load_preferences(data)['new_device_proxy'])
    c.update_device(restored,'02:00:00:00:00:01','192.168.50.111')
    c.update_device(restored,'02:00:00:00:00:02','192.168.50.112')
    self.assertTrue(restored['02:00:00:00:00:01']['enabled'])
    self.assertFalse(restored['02:00:00:00:00:02']['enabled'])
    c.update_device(restored,'02:00:00:00:00:03','192.168.50.113')
    self.assertFalse(restored['02:00:00:00:00:03']['enabled'])
