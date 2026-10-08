"""Read-only Huawei TC7102 device-table client, matching its shipped SCRAM implementation."""
import hashlib, hmac, http.cookiejar, json, re, secrets
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request

class RouterClient:
    def __init__(self, password, url):
        self.url=url.rstrip("/")
        self.password=password
        self.opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf={}
    def request(self, path, data=None):
        if path not in ('/html/index.html','/api/system/user_login_nonce','/api/system/user_login_proof','/api/system/HostInfo'):
            raise ValueError('Unsupported router endpoint')
        payload=None if data is None else json.dumps({'data':data,'csrf':self.csrf}).encode()
        req=Request(self.url+path,data=payload,headers={'Content-Type':'application/json; charset=utf-8','X-Requested-With':'XMLHttpRequest','_ResponseFormat':'JSON'})
        with self.opener.open(req,timeout=10) as response: raw=response.read(1048576)
        if path.endswith('.html'): return raw.decode()
        result=json.loads(raw)
        if isinstance(result,dict) and result.get('csrf_token'):
            self.csrf={k:result[k] for k in ('csrf_param','csrf_token')}
        return result
    def login(self):
        html=self.request('/html/index.html')
        self.csrf={k:re.search(r'name="'+k+r'" content="([^"]+)"',html).group(1) for k in ('csrf_param','csrf_token')}
        nonce=secrets.token_hex(32)
        r=self.request('/api/system/user_login_nonce',{'username':'admin','firstnonce':nonce})
        if r.get('err')!=0: raise RuntimeError('Router authentication unavailable')
        iterations=int(r['iterations'])
        if not 1<=iterations<=1000000: raise ValueError('Invalid iterations')
        salted=hashlib.pbkdf2_hmac('sha256',self.password.encode(),bytes.fromhex(r['salt']),iterations)
        # Firmware CryptoJS.HmacSHA256(message, key) uses this argument order.
        digest=lambda message,key:hmac.new(key,message,hashlib.sha256).digest()
        client=digest(salted,b'Client Key'); server=digest(salted,b'Server Key')
        message=(nonce+','+r['servernonce']+','+r['servernonce']).encode()
        signature=digest(hashlib.sha256(client).digest(),message)
        proof=bytes(a^b for a,b in zip(client,signature)).hex()
        result=self.request('/api/system/user_login_proof',{'clientproof':proof,'finalnonce':r['servernonce']})
        if result.get('err')!=0 or not hmac.compare_digest(result.get('serversignature',''),digest(server,message).hex()):
            raise RuntimeError('Router authentication failed')
    def devices(self):
        try: result=self.request('/api/system/HostInfo')
        except HTTPError as e:
            if e.code not in (401,403,404): raise
            result=None
        if not isinstance(result,list):
            self.login(); result=self.request('/api/system/HostInfo')
        if not isinstance(result,list): raise RuntimeError('Router device table unavailable')
        return normalize(result)

def normalize(rows):
    result={}
    for row in rows:
        mac=str(row.get('MACAddress','')).lower()
        if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac): continue
        def clean(value):
            text=str(value or '').strip()[:100]
            return '' if text.lower() in ('default','unknown','none','localhost') else text
        name=clean(row.get('ActualName')) or clean(row.get('HostName'))
        if name.lower() in (mac,mac.replace(':','-')) or name.startswith('未知设备-'): name=''
        fields={'router_source':'华为','router_name':name,'router_brand':clean(row.get('ActualManu')) or clean(row.get('DevBrands')),'router_type':clean(row.get('IconType')),'router_model':clean(row.get('ModelName')) or clean(row.get('DeviceModel'))}
        previous=result.setdefault(mac,{})
        for key,value in fields.items():
            if value or key not in previous: previous[key]=value
    return result
