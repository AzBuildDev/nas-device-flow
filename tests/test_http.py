import json,sys,tempfile,threading,unittest
from pathlib import Path
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import server as c
class HTTPTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  root=Path(self.tmp.name);data=root/'control-center';data.mkdir();(data/'admin-secret').write_text('fictional-admin-password');(root/'secret').write_text('fictional-core-api-key')
  self.patches=[patch.object(c,'ROOT',root),patch.object(c,'DATA',data),patch.object(c,'SESSIONS',{}),patch.object(c,'FAILURES',{})]
  for p in self.patches:p.start();self.addCleanup(p.stop)
  self.http=ThreadingHTTPServer(('127.0.0.1',0),c.Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start()
  self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)
 def request(self,path,body=None,headers=None):
  conn=HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
  h={'Content-Type':'application/json'};h.update(headers or {})
  conn.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),h)
  r=conn.getresponse();result=(r.status,dict(r.getheaders()),r.read());conn.close();return result
 def login(self):return self.request('/api/login',{'password':'fictional-admin-password'})
 def test_private_api_requires_login(self):
  self.assertEqual(self.request('/api/stats')[0],401)
 def test_core_secret_cannot_login(self):
  self.assertEqual(self.request('/api/login',{'password':'fictional-core-api-key'})[0],401)
 def test_cookie_and_csrf_required(self):
  status,headers,body=self.login();self.assertEqual(status,200)
  cookie=headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
  self.assertEqual(self.request('/api/logout',{}, {'Cookie':cookie})[0],403)
  token=json.loads(body)['csrf'];self.assertEqual(self.request('/api/logout',{}, {'Cookie':cookie,'X-CSRF-Token':token})[0],200)
 def test_foreign_origin_rejected(self):
  self.assertEqual(self.request('/api/login',{'password':'fictional-admin-password'},{'Origin':'https://example.invalid'})[0],403)
 def test_login_rate_limit(self):
  for _ in range(8):self.assertEqual(self.request('/api/login',{'password':'wrong'})[0],401)
  self.assertEqual(self.login()[0],429)
 def test_page_no_core_secret_and_decimal_units(self):
  status,_,body=self.request('/');self.assertEqual(status,200)
  self.assertNotIn(b'fictional-core-api-key',body);self.assertNotIn(b'{{GATEWAY}}',body)
  self.assertIn(b'while(v>=1000',body);self.assertNotIn(b'MiB',body)
if __name__=='__main__':unittest.main()
