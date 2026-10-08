"""Guard translated controls and authentication errors against partial localization."""
import json,re,unittest
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
  self.en=json.loads(self.html.split('const EN=')[1].split(';\nfunction t')[0])
 def test_every_static_control_and_help_text_has_english(self):
  page=StaticText();page.feed(self.html)
  keys={x for x in page.keys if re.search('[\u4e00-\u9fff]',x) and x!='中文'}
  self.assertFalse(keys-self.en.keys())
  self.assertTrue(all(self.en[key] and not re.search('[\u4e00-\u9fff]',self.en[key]) for key in keys))
 def test_dynamic_translated_literals_and_server_errors_are_covered(self):
  script=self.html.split('function text(')[1]
  keys=set(re.findall(r"\bt\('([^']*[\u4e00-\u9fff][^']*)'\)",script))
  errors=set(re.findall(r"\{'error':'([^']+)'",(APP/'server.py').read_text()))
  self.assertFalse((keys|errors)-self.en.keys())
 def test_language_and_new_device_policy_are_distinct_controls(self):
  self.assertIn('id="language"',self.html);self.assertIn('id="defaultpolicy"',self.html)
  self.assertIn("localStorage.setItem('ndf-language'",self.html)
  self.assertIn("request('/api/settings',{new_device_proxy:",self.html)

if __name__=='__main__':unittest.main()
