"""Guard translated controls and authentication errors against partial localization."""
import json,re,shutil,subprocess,unittest
from html.parser import HTMLParser
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/'app'

class StaticText(HTMLParser):
 def __init__(self):super().__init__();self.skipping=False;self.keys=set()
 def handle_starttag(self,tag,attrs):
  if tag in ('style','script'):self.skipping=True
  for key,value in attrs:
   if key in ('title','placeholder','aria-label') and value:self.keys.add(value)
 def handle_endtag(self,tag):
  if tag in ('style','script'):self.skipping=False
 def handle_data(self,value):
  if not self.skipping:self.keys.add(value.strip())

class LanguageTests(unittest.TestCase):
 def setUp(self):
  self.html=(APP/'index.html').read_text()
  self.catalogs={name:json.loads(self.html.split('const '+name+'=')[1].split(';\n')[0]) for name in ('EN','JA','ES','FR','KO')}
  self.en=self.catalogs['EN']
 def test_every_static_control_and_help_text_has_english(self):
  page=StaticText();page.feed(self.html)
  keys={x for x in page.keys if re.search('[\u4e00-\u9fff]',x) and x not in ('中文','日本語')}
  self.assertFalse(keys-self.en.keys())
  self.assertTrue(all(self.en[key] and not re.search('[\u4e00-\u9fff]',self.en[key]) for key in keys))
 def test_all_languages_cover_same_messages_and_keep_placeholders(self):
  for name,catalog in self.catalogs.items():
   with self.subTest(language=name):
    self.assertEqual(set(catalog),set(self.en))
    for key,value in catalog.items():
     self.assertTrue(value.strip(),(name,key))
     self.assertEqual(re.findall(r'\{\{[^}]+\}\}',key),re.findall(r'\{\{[^}]+\}\}',value),(name,key))
     if name in ('ES','FR','KO'):
      self.assertFalse(re.search('[\u4e00-\u9fff]',value),(name,key))
 def test_dynamic_translated_literals_and_server_errors_are_covered(self):
  script=self.html.split('function text(')[1]
  keys=set(re.findall(r"\bt\('([^']*[\u4e00-\u9fff][^']*)'\)",script))
  errors=set(re.findall(r"\{'error':'([^']+)'",(APP/'server.py').read_text()))
  self.assertFalse((keys|errors)-self.en.keys())
  demo_errors=set(re.findall(r"\{'error':'([^']+)'",(APP.parent/'scripts/demo.py').read_text()))
  self.assertFalse(demo_errors-self.en.keys())
 def test_router_source_has_no_huawei_fallback(self):
  self.assertNotIn("x.router_source||t('华为')",self.html)
  self.assertIn("t(x.router_source)||t('路由器')",self.html)
 def test_language_and_new_device_policy_are_distinct_controls(self):
  self.assertIn('id="language"',self.html);self.assertIn('id="defaultpolicy"',self.html)
  self.assertIn("localStorage.setItem('ndf-language'",self.html)
  self.assertIn("request('/api/settings',{new_device_proxy:",self.html)
 def run_language_script(self,assertions):
  node=shutil.which('node')
  if not node:self.skipTest('Node.js required for runtime language checks')
  start=self.html.index("let languagePreference='auto';")
  end=self.html.index('function dateTime',start)
  script="const assert=require('node:assert/strict');let stored=null;const localStorage={getItem:()=>stored};const navigator={languages:['en-US'],language:'en-US'};\n"+self.html[start:end]+assertions
  result=subprocess.run([node,'-e',script],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_browser_region_variants_and_fallback(self):
  self.run_language_script("""
for(const [locale,expected] of [['ko-KR','ko'],['ko','ko'],['ja-JP','ja'],['es-MX','es'],['es-ES','es'],['fr-CA','fr'],['fr-FR','fr'],['zh-TW','zh-CN'],['en-GB','en'],['de-DE','en']])assert.equal(resolveLanguage('auto',[locale]),expected);
assert.equal(resolveLanguage('auto',['de-DE','ja-JP','en']), 'ja');
assert.equal(resolveLanguage('auto',[]),'en');
assert.equal(resolveLanguage('invalid',['fr-FR']),'fr');
for(const language of LANGUAGES)assert.equal(resolveLanguage(language,['ja-JP']),language);
navigator.languages=[];navigator.language='es-AR';assert.equal(currentLanguage(),'es');
""")
 def test_switch_back_and_forth_and_translate_dynamic_errors(self):
  self.run_language_script("""
for(const language of ['ko','ja','es','fr','en','zh-CN','ko']){
 languagePreference=language;
 const expected=language==='zh-CN'?'设置':CATALOGS[language]['设置'];
 assert.equal(t('设置'),expected);
 assert.equal(t('My personal device'),'My personal device');
 assert.equal(t(''), '');
 assert.equal(t(null), '');
 assert.equal(t('设备同步失败：timeout'),language==='zh-CN'?'设备同步失败：timeout':CATALOGS[language]['设备同步失败：']+'timeout');
 assert.ok(!t('密码不正确').includes('密码')||language==='zh-CN');
}
for(const [language,label]of [['ko','한국어'],['ja','日本語'],['es','Español'],['fr','Français']])assert.ok("""+json.dumps(self.html.split('<select id="language">')[1].split('</select>')[0])+""".includes('value="'+language+'">'+label));
""")

if __name__=='__main__':unittest.main()
