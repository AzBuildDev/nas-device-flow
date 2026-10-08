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
  self.assertEqual(self.request('/api/settings')[0],401)
  self.assertEqual(self.request('/api/password',{'new_password':'irrelevant'})[0],401)
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
 def auth(self):
  _,headers,body=self.login()
  return {'Cookie':headers['Set-Cookie'],'X-CSRF-Token':json.loads(body)['csrf']}
 def test_settings_csrf_validation_and_persistence(self):
  auth=self.auth()
  self.assertEqual(self.request('/api/settings',{'new_device_proxy':True},{'Cookie':auth['Cookie']})[0],403)
  self.assertEqual(self.request('/api/settings',{'new_device_proxy':'true'},auth)[0],400)
  self.assertEqual(self.request('/api/settings',{'new_device_proxy':True},auth)[0],200)
  status,_,body=self.request('/api/settings',headers=auth)
  self.assertEqual(status,200);self.assertTrue(json.loads(body)['preferences']['new_device_proxy'])
  self.assertNotIn(b'fictional-admin-password',body);self.assertNotIn(b'fictional-core-api-key',body)
 def test_password_change_invalidates_all_sessions_and_preserves_core_secret(self):
  auth=self.auth();other=self.auth()
  payload={'current_password':'fictional-admin-password','new_password':'fictional-new-admin-password','confirm_password':'fictional-new-admin-password'}
  self.assertEqual(self.request('/api/password',payload,auth)[0],200)
  self.assertEqual(self.request('/api/settings',headers=auth)[0],401)
  self.assertEqual(self.request('/api/settings',headers=other)[0],401)
  self.assertEqual(self.login()[0],401)
  self.assertEqual(self.request('/api/login',{'password':payload['new_password']})[0],200)
  self.assertEqual((c.ROOT/'secret').read_text(),'fictional-core-api-key')
  self.assertEqual((c.DATA/'admin-secret').stat().st_mode & 0o777,0o600)
 def test_password_errors_preserve_credentials(self):
  auth=self.auth();payload={'current_password':'wrong','new_password':'fictional-new-admin-password','confirm_password':'fictional-new-admin-password'}
  self.assertEqual(self.request('/api/password',payload,auth)[0],403)
  payload['current_password']='fictional-admin-password';payload['confirm_password']='different'
  self.assertEqual(self.request('/api/password',payload,auth)[0],400)
  payload['new_password']=payload['confirm_password']='short'
  self.assertEqual(self.request('/api/password',payload,auth)[0],400)
  payload['new_password']=payload['confirm_password']='fictional-core-api-key'
  self.assertEqual(self.request('/api/password',payload,auth)[0],400)
  self.assertEqual(self.request('/api/settings',headers=auth)[0],200)
  self.assertEqual((c.DATA/'admin-secret').read_text(),'fictional-admin-password')
 def test_password_verification_is_rate_limited(self):
  auth=self.auth();payload={'current_password':'wrong','new_password':'fictional-new-admin-password','confirm_password':'fictional-new-admin-password'}
  for _ in range(8):self.assertEqual(self.request('/api/password',payload,auth)[0],403)
  self.assertEqual(self.request('/api/password',payload,auth)[0],429)
 def test_dhcp_enable_requires_login_csrf_and_explicit_confirmations(self):
  payload={'action':'enable','tested_client':True,'main_router_dhcp_off':True,'sole_dhcp_server':True}
  self.assertEqual(self.request('/api/dhcp',payload)[0],401)
  auth=self.auth()
  self.assertEqual(self.request('/api/dhcp',payload,{'Cookie':auth['Cookie']})[0],403)
  with patch.object(c,'core') as core:
   for key in ('tested_client','main_router_dhcp_off','sole_dhcp_server'):
    for value in (False,'true'):
     self.assertEqual(self.request('/api/dhcp',dict(payload,**{key:value}),auth)[0],400)
   core.assert_not_called()
  self.assertFalse((c.DATA/'dhcp.enabled').exists())
 def test_dhcp_marker_changes_only_after_core_check_and_recovery_confirmation(self):
  auth=self.auth();payload={'action':'enable','tested_client':True,'main_router_dhcp_off':True,'sole_dhcp_server':True}
  with patch.object(c,'core',side_effect=OSError('fixture')):
   self.assertEqual(self.request('/api/dhcp',payload,auth)[0],503)
  self.assertFalse((c.DATA/'dhcp.enabled').exists())
  with patch.object(c,'core',return_value={'version':'fixture'}):
   self.assertEqual(self.request('/api/dhcp',payload,auth)[0],200)
  self.assertTrue((c.DATA/'dhcp.enabled').exists())
  self.assertEqual((c.DATA/'dhcp.enabled').stat().st_mode&0o777,0o600)
  self.assertEqual(self.request('/api/dhcp',{'action':'disable'},auth)[0],400)
  self.assertTrue((c.DATA/'dhcp.enabled').exists())
  self.assertEqual(self.request('/api/dhcp',{'action':'disable','confirm_recovery':True},auth)[0],200)
  self.assertFalse((c.DATA/'dhcp.enabled').exists())
 def test_dhcp_settings_distinguish_requested_and_running(self):
  auth=self.auth();(c.DATA/'dhcp.enabled').touch()
  with patch.object(c,'DHCP',None):
   status,_,body=self.request('/api/settings',headers=auth)
  self.assertEqual(status,200)
  self.assertEqual(json.loads(body)['dhcp'],{'requested':True,'running':False,'authoritative':False})
if __name__=='__main__':unittest.main()
