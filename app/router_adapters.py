"""Optional, read-only router name sources. OpenWrt/RouterOS are not hardware verified."""
import base64, json, re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from huawei_router import RouterClient

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ValueError('Router redirects are not supported')

def endpoint(value):
    u=urlsplit(value)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        raise ValueError('Expected router origin without credentials or path')
    return value.rstrip('/')

def identity(mac,name,source):
    mac=str(mac or '').lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac): return None
    name=str(name or '').strip()[:100]
    if name in ('*','localhost') or name.lower() in (mac,mac.replace(':','-')): name=''
    return mac,dict(router_name=name,router_brand='',router_type='',router_model='',router_source=source)

class JsonClient:
    def __init__(self,url,username,password):
        self.url=endpoint(url);self.username=username;self.password=password
        self.opener=build_opener(NoRedirect())
    def request(self,path,body=None,headers=None):
        req=Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json',**(headers or {})})
        with self.opener.open(req,timeout=10) as r: return json.loads(r.read(1048576))

class OpenWrtClient(JsonClient):
    def call(self,token,obj,method,args):
        result=self.request('/ubus',{'jsonrpc':'2.0','id':1,'method':'call','params':[token,obj,method,args]})
        values=result.get('result')
        if not isinstance(values,list) or len(values)<2 or values[0]!=0: raise RuntimeError('OpenWrt RPC unavailable or access denied')
        return values[1]
    def devices(self):
        login=self.call('0'*32,'session','login',{'username':self.username,'password':self.password,'timeout':120})
        data=self.call(login['ubus_rpc_session'],'file','read',{'path':'/tmp/dhcp.leases'})
        return self.parse(data.get('data',''))
    @staticmethod
    def parse(text):
        result={}
        for line in text.splitlines():
            parts=line.split()
            if len(parts)<4: continue
            item=identity(parts[1],parts[3],'OpenWrt')
            if item: result[item[0]]=item[1]
        return result

class RouterOSClient(JsonClient):
    def devices(self):
        auth=base64.b64encode((self.username+':'+self.password).encode()).decode()
        rows=self.request('/rest/ip/dhcp-server/lease',headers={'Authorization':'Basic '+auth})
        return self.parse(rows)
    @staticmethod
    def parse(rows):
        if not isinstance(rows,list): raise RuntimeError('RouterOS lease table unavailable')
        result={}
        for row in rows:
            item=identity(row.get('mac-address'),row.get('host-name'),'MikroTik')
            if item: result[item[0]]=item[1]
        return result

def create_client(directory):
    directory=Path(directory)
    config_path=directory/'router-adapter.json'
    if not config_path.exists(): return None
    config=json.loads(config_path.read_text());kind=config.get('type','none')
    if kind=='none': return None
    password_path=directory/config.get('password_file','router-password')
    if password_path.resolve().parent!=directory.resolve(): raise ValueError('Password file must be in controller directory')
    password=password_path.read_text().strip()
    if kind=='huawei': return RouterClient(password,endpoint(config['url']))
    classes={'openwrt':OpenWrtClient,'mikrotik':RouterOSClient}
    if kind not in classes: raise ValueError('Unsupported router type')
    return classes[kind](config['url'],config['username'],password)
