"""Exercise browser theme preference, system updates and pre-paint rendering."""
import json,re,shutil,subprocess,unittest
from pathlib import Path

HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

class ThemeTests(unittest.TestCase):
 def run_script(self,source,assertions,saved=None,dark=False):
  node=shutil.which('node')
  if not node:self.skipTest('Node.js required for theme runtime checks')
  harness="""
const assert=require('node:assert/strict');
let saved=SAVED;
const localStorage={getItem:()=>saved,setItem:(key,value)=>{assert.equal(key,'ndf-theme');saved=value;}};
const media={matches:DARK,addEventListener:(event,callback)=>{assert.equal(event,'change');media.change=callback;}};
const listeners={};const window={matchMedia:()=>media,addEventListener:(event,callback)=>listeners[event]=callback};
const document={documentElement:{dataset:{}}};const control={value:''};const $=id=>{assert.equal(id,'theme');return control;};
const fetch=()=>{throw Error('Theme changes must not call a network API');};
""".replace('SAVED',json.dumps(saved)).replace('DARK',json.dumps(dark))
  result=subprocess.run([node,'-e',harness+source+assertions],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def main_script(self):
  return "let themePreference='auto';"+HTML.split("let themePreference='auto';")[1].split('</script>')[0]
 def test_default_follows_system_and_tracks_changes(self):
  self.run_script(self.main_script(),"""
assert.equal(document.documentElement.dataset.theme,'light');assert.equal(control.value,'auto');
media.matches=true;media.change();assert.equal(document.documentElement.dataset.theme,'dark');
media.matches=false;media.change();assert.equal(document.documentElement.dataset.theme,'light');
""")
 def test_manual_choice_overrides_system_and_persists(self):
  self.run_script(self.main_script(),"""
assert.equal(document.documentElement.dataset.theme,'dark');
control.value='light';control.onchange();assert.equal(saved,'light');assert.equal(document.documentElement.dataset.theme,'light');
media.matches=true;media.change();assert.equal(document.documentElement.dataset.theme,'light');
control.value='dark';control.onchange();assert.equal(saved,'dark');
media.matches=false;media.change();assert.equal(document.documentElement.dataset.theme,'dark');
control.value='auto';control.onchange();assert.equal(saved,'auto');assert.equal(document.documentElement.dataset.theme,'light');
""",saved='dark')
 def test_cross_tab_changes_and_invalid_preferences(self):
  self.run_script(self.main_script(),"""
assert.equal(control.value,'auto');assert.equal(document.documentElement.dataset.theme,'dark');
saved='light';listeners.storage({key:'ndf-language'});assert.equal(control.value,'auto');
listeners.storage({key:'ndf-theme'});assert.equal(control.value,'light');assert.equal(document.documentElement.dataset.theme,'light');
saved=null;listeners.storage({key:null});assert.equal(control.value,'auto');assert.equal(document.documentElement.dataset.theme,'dark');
""",saved='invalid',dark=True)
 def test_prepaint_script_matches_saved_preference(self):
  boot=re.findall(r'<script>(.*?)</script>',HTML,re.S)[0]
  self.assertLess(HTML.index('<script>'),HTML.index('<style>'))
  for saved,system,expected in [(None,True,'dark'),('light',True,'light'),('dark',False,'dark'),('invalid',False,'light')]:
   with self.subTest(saved=saved,system=system):self.run_script(boot,'assert.equal(document.documentElement.dataset.theme,'+json.dumps(expected)+');',saved,system)
 def test_storage_unavailable_still_renders_and_switches(self):
  source="localStorage.getItem=()=>{throw Error('blocked');};localStorage.setItem=()=>{throw Error('blocked');};"+self.main_script()
  self.run_script(source,"control.value='dark';control.onchange();assert.equal(document.documentElement.dataset.theme,'dark');")

if __name__=='__main__':unittest.main()
