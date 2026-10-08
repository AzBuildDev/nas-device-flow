#!/usr/bin/env python3
"""LAN device controller. No Docker socket, shell interpolation, or host network access."""
import atexit, copy, hashlib, hmac, http.cookies, ipaddress, json, os, re, secrets, signal, socket, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import yaml
from device_names import discover_names
from router_adapters import create_client
from traffic_stats import TrafficStats
from device_traffic import DeviceTraffic, proxy_nodes, ip_owners
from subscriptions import Subscriptions
from urllib.parse import quote
from settings import Settings
from access_status import AccessStatus, valid_leases
from preferences import load_preferences, save_preferences

ROOT=Path(os.environ.get('NDF_DATA_ROOT','/data'))
DATA=ROOT/'control-center'
SETTINGS=Settings.load(DATA/'settings.json')
HTML=Path(__file__).with_name('index.html')
MAC=re.compile(r'^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$')
LOCK=threading.RLock()
STATS=TrafficStats()
ACCESS=AccessStatus()
DEVICE_TRAFFIC=None
ROUTER_STATUS={'ok':False,'last_sync':0,'matched':0}
SESSIONS={}; FAILURES={}; DHCP=None; LAST_ERROR=''; APPLIED=None
def valid_ip(value):
    return SETTINGS.valid_ip(value)

def atomic(path, text):
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(text); os.chmod(tmp,0o600); tmp.replace(path)

def core(path, method='GET', body=None):
    secret=(ROOT/'secret').read_text().strip()
    req=Request(SETTINGS.core_url+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'})
    with urlopen(req,timeout=12) as r:
        raw=r.read(); return json.loads(raw) if raw else {}

def load():
    try: return json.loads((DATA/'devices.json').read_text())
    except FileNotFoundError: return {}

def save(devices): atomic(DATA/'devices.json',json.dumps(devices,ensure_ascii=False,indent=2))

def render(base,devices):
    result=copy.deepcopy(base)
    # Only enabled devices enter domestic/foreign routing. Everything else is DIRECT.
    ips=sorted({d['ip'] for d in devices.values() if d.get('enabled') and valid_ip(d.get('ip'))})
    result['sub-rules']={'smart-routing':base['rules']}
    result['rules']=['SUB-RULE,(SRC-IP-CIDR,'+ip+'/32),smart-routing' for ip in ips]+['MATCH,DIRECT']
    # All clients use direct domestic DoH for DNS; only enabled clients' traffic uses proxy.
    result.setdefault('dns',{})['nameserver']=SETTINGS.direct_dns
    return result

def reserve_enabled(devices):
    # Reserve enabled IPs so an expired lease cannot grant proxy access to a new MAC.
    fixed=DATA/'fixed.hosts'
    hosts={}
    if fixed.exists():
        for line in fixed.read_text().splitlines():
            if line and not line.startswith('#'): hosts[line.split(',')[0]]=line
    for mac,d in devices.items():
        if d.get('enabled') and valid_ip(d.get('ip')):
            if mac not in hosts: hosts[mac]=mac+','+d['ip']+',12h'
    value='\n'.join(hosts.values())+'\n'
    path=DATA/'dhcp.hosts'
    if not path.exists() or path.read_text()!=value:
        atomic(path,value)
        if DHCP is not None and DHCP.poll() is None: DHCP.send_signal(signal.SIGHUP)

def apply(devices, force=False):
    global APPLIED
    reserve_enabled(devices)
    base=yaml.safe_load((DATA/'base.yaml').read_text())
    config=yaml.safe_dump(render(base,devices),allow_unicode=True,sort_keys=False)
    fingerprint=hashlib.sha256(config.encode()).hexdigest()
    if not force and APPLIED==fingerprint: return
    old=(ROOT/'config.yaml').read_text()
    atomic(ROOT/'config.yaml',config)
    try:
        core('/configs?force=true','PUT',{'path':SETTINGS.core_config_path})
        rules=core('/rules')['rules']
        expected=sum(1 for d in devices.values() if d.get('enabled') and valid_ip(d.get('ip')))
        if not rules or rules[-1]['type']!='Match' or rules[-1]['proxy']!='DIRECT': raise RuntimeError('规则验收失败')
        if sum(r['type']=='SubRules' for r in rules)!=expected: raise RuntimeError('设备规则数量不符：'+str([(r['type'],r['proxy']) for r in rules]))
    except Exception:
        atomic(ROOT/'config.yaml',old)
        try: core('/configs?force=true','PUT',{'path':SETTINGS.core_config_path})
        except Exception: pass
        raise
    APPLIED=fingerprint

def close_connections(ip):
    failures=0
    for c in core('/connections').get('connections') or []:
        if c.get('metadata',{}).get('sourceIP')==ip:
            try: core('/connections/'+c['id'],'DELETE')
            except Exception: failures+=1
    return failures

def update_device(devices,mac,ip,name='',source='neighbor',seen=False):
    mac=mac.lower()
    if not MAC.fullmatch(mac) or not valid_ip(ip): return
    # An IP belongs to one active MAC; revoke an old mapping before granting any new one.
    for other,d in devices.items():
        if other!=mac and d.get('ip')==ip: d['ip']=''; d['online']=False
    if mac not in devices:
        devices[mac]={'mac':mac,'name':'','enabled':load_preferences(DATA)['new_device_proxy'],'first_seen':int(time.time())}
    d=devices[mac]
    d['ip']=ip; d['source']=source
    if name and name!='*': d['hostname']=name[:80]
    if seen: d['last_seen']=int(time.time())
    d['online']=time.time()-d.get('last_seen',0)<180

def sync():
    with LOCK:
        devices=load()
        leased={}
        leases=DATA/'dnsmasq.leases'
        if leases.exists():
            for line in leases.read_text().splitlines():
                f=line.split()
                if len(f)>=4 and (int(f[0])==0 or int(f[0])>time.time()):
                    update_device(devices,f[1],f[2],f[3],'dhcp')
                    leased[f[1].lower()]=f[2]
        neighbors=json.loads(subprocess.check_output(['ip','-j','-4','neigh','show','dev',SETTINGS.interface],text=True))
        for n in neighbors:
            if n.get('lladdr') in leased and leased[n['lladdr']]!=n.get('dst'): continue
            if n.get('lladdr') and n.get('dst') and not set(n.get('state',[])) & {'FAILED','INCOMPLETE'}:
                update_device(devices,n['lladdr'],n['dst'],source='dhcp' if any(d.get('ip')==n['dst'] and d.get('source')=='dhcp' for d in devices.values()) else 'neighbor',seen='REACHABLE' in n.get('state',[]))
        for d in devices.values(): d['online']=time.time()-d.get('last_seen',0)<180
        apply(devices); save(devices)
        if core('/configs').get('mode')!='rule': core('/configs','PATCH',{'mode':'rule'})

def scan_ip(ip):
    subprocess.run(['ping','-c','1','-W','1',ip],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)

def sync_names():
    with LOCK:
        devices=load()
        ips=[d['ip'] for d in devices.values() if valid_ip(d.get('ip'))]
    names=discover_names(ips)
    with LOCK:
        devices=load()
        for d in devices.values():
            if d.get('mdns_name','').casefold()=='localhost': d.pop('mdns_name',None)
            if d.get('ip') in names:
                d['mdns_name']=names[d['ip']]
                d['mdns_name_seen']=int(time.time())
        save(devices)

def subscription_apply():
    apply(load(),True)
    provider=core('/providers/proxies/'+quote(SETTINGS.provider,safe=''))
    if not provider.get('proxies'): raise RuntimeError('订阅未加载节点')

def subscription_info():
    with LOCK: result=Subscriptions(DATA,atomic,SETTINGS.provider).summaries()
    result.update(available=False,node='',node_count=0,updated='',usage=None)
    try:
        provider=core('/providers/proxies/'+quote(SETTINGS.provider,safe=''))
        selected=core('/proxies/'+quote(SETTINGS.proxy_group,safe='')).get('now','')
        if selected==SETTINGS.auto_group: selected=core('/proxies/'+quote(SETTINGS.auto_group,safe='')).get('now',SETTINGS.auto_group)
        usage=provider.get('subscriptionInfo')
        if isinstance(usage,dict): usage={k:usage[k] for k in ('Upload','Download','Total','Expire') if isinstance(usage.get(k),(int,float))}
        result.update(available=True,node=selected,node_count=len(provider.get('proxies') or []),updated=provider.get('updatedAt',''),usage=usage)
    except Exception: pass
    return result

def collect_stats():
    while True:
        try:
            req=Request(SETTINGS.core_url+'/traffic',headers={'Authorization':'Bearer '+(ROOT/'secret').read_text().strip()})
            with urlopen(req,timeout=8) as stream:
                last_connections=0;last_nodes=0;nodes=set()
                while True:
                    line=stream.readline(65536)
                    if not line: raise OSError('Telemetry stream ended')
                    connections=None
                    if time.monotonic()-last_connections>=1:
                        if time.monotonic()-last_nodes>=30:
                            nodes=proxy_nodes(core('/proxies').get('proxies',{}),core('/providers/proxies').get('providers',{}));last_nodes=time.monotonic()
                        connections=core('/connections');last_connections=time.monotonic()
                        with LOCK: owners=ip_owners(load())
                        ACCESS.sample(connections.get('connections') or [],owners)
                        DEVICE_TRAFFIC.sample(connections.get('connections') or [],owners,nodes)
                    STATS.update(json.loads(line),connections)
        except Exception:
            STATS.failed();time.sleep(3)

def router_names():
    client=None
    while True:
        try:
            if client is None: client=create_client(DATA)
            names={} if client is None else client.devices()
            with LOCK:
                devices=load(); matched=0
                for mac,d in devices.items():
                    if mac in names:
                        d.update(names[mac]); d['router_seen']=int(time.time()); matched+=1
                save(devices)
                ROUTER_STATUS.update(ok=True,last_sync=int(time.time()),matched=matched)
            delay=60
        except Exception:
            ROUTER_STATUS['ok']=False
            client=None; delay=300
        time.sleep(delay)

def discovery():
    global LAST_ERROR
    count=0
    while True:
        try:
            if count%6==0:
                with ThreadPoolExecutor(max_workers=12) as pool: list(pool.map(scan_ip,SETTINGS.scan_hosts()))
            sync()
            if count%6==0:
                try: sync_names()
                except OSError: pass
            LAST_ERROR=''
        except Exception as e:
            LAST_ERROR='设备同步失败：'+type(e).__name__; print(LAST_ERROR,flush=True)
        count+=1; time.sleep(10)

def dhcp_supervisor():
    global DHCP
    while True:
        enabled=(DATA/'dhcp.enabled').exists()
        if enabled and (DHCP is None or DHCP.poll() is not None):
            DHCP=subprocess.Popen(['dnsmasq','--keep-in-foreground','--conf-file='+str(DATA/'dnsmasq.conf')])
        elif not enabled and DHCP is not None and DHCP.poll() is None:
            DHCP.terminate(); DHCP.wait(timeout=5); DHCP=None
        time.sleep(3)

class Handler(BaseHTTPRequestHandler):
    server_version='NASDeviceFlow/0.1.0-rc.4'
    def log_message(self,*args): pass
    def send(self,status,body,ctype='application/json',cookie=None):
        data=body.encode() if isinstance(body,str) else json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type',ctype+'; charset=utf-8'); self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(data)
    def session(self):
        try: token=http.cookies.SimpleCookie(self.headers.get('Cookie',''))['session'].value
        except (KeyError,http.cookies.CookieError): return None
        s=SESSIONS.get(token)
        return s if s and s['expires']>time.time() else None
    def do_GET(self):
        if self.path=='/health': return self.send(200,{'ok':True})
        if self.path=='/': return self.send(200,HTML.read_text().replace('{{CORE_URL}}',SETTINGS.core_url).replace('{{GATEWAY}}',SETTINGS.core_ip),'text/html')
        s=self.session()
        if not s: return self.send(401,{'error':'请登录'})
        if self.path=='/api/settings':
            with LOCK: preferences=load_preferences(DATA)
            return self.send(200,{'preferences':preferences,'gateway':SETTINGS.core_ip,'upstream':SETTINGS.upstream,'panel_ip':SETTINGS.panel_ip,'subnet':SETTINGS.subnet,'routing':'China direct / other destinations via PROXY','app_version':'0.1.0-rc.4','csrf':s['csrf']})
        if self.path=='/api/subscriptions':
            try: return self.send(200,subscription_info())
            except Exception: return self.send(503,{'error':'订阅信息读取失败'})
        if self.path=='/api/stats':
            result=STATS.snapshot();result['device_traffic']=DEVICE_TRAFFIC.snapshot()
            return self.send(200,result)
        if self.path=='/api/devices':
            with LOCK:
                devices=list(load().values())
                try: leases=valid_leases((DATA/'dnsmasq.leases').read_text())
                except OSError: leases=set()
            traffic=DEVICE_TRAFFIC.snapshot()
            for d in devices:
                d.update(ACCESS.status(d,leases))
                d['proxy_traffic']=traffic['devices'].get(d['mac'],{'upload':0,'download':0,'total':0})
                d['proxy_traffic_ok']=traffic['ok']
                d['proxy_traffic_since']=traffic['since']
                d['is_this_device']=d.get('ip')==self.client_address[0]
                d['label']=d.get('name') or d.get('router_name') or d.get('mdns_name') or d.get('hostname') or ('这台设备' if d['is_this_device'] else '未命名设备')
            devices.sort(key=lambda d:(not d.get('online'),not d.get('enabled'),d.get('label','')))
            healthy=True
            try: version=core('/version').get('version','')
            except Exception: version=''; healthy=False
            return self.send(200,{'devices':devices,'preferences':load_preferences(DATA),'router_sync':dict(ROUTER_STATUS),'csrf':s['csrf'],'core_ok':healthy,'version':version,'dhcp':DHCP is not None and DHCP.poll() is None,'error':LAST_ERROR,'gateway':SETTINGS.core_ip,'client_ip':self.client_address[0]})
        return self.send(404,{'error':'不存在'})
    def do_POST(self):
        # JSON + SameSite cookie + CSRF token + exact Origin restrict LAN cross-site attacks.
        origin=self.headers.get('Origin')
        if origin and origin!=SETTINGS.panel_origin: return self.send(403,{'error':'来源不允许'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json': return self.send(415,{'error':'需要 JSON'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if length<=0 or length>4096: raise ValueError()
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict): raise ValueError()
        except (ValueError,json.JSONDecodeError): return self.send(400,{'error':'请求无效'})
        if self.path=='/api/login':
            ip=self.client_address[0]; now=time.time()
            attempts=[t for t in FAILURES.get(ip,[]) if now-t<300]
            if len(attempts)>=8: return self.send(429,{'error':'尝试过多，请五分钟后再试'})
            supplied=body.get('password','')
            if not isinstance(supplied,str) or not hmac.compare_digest(supplied.encode(),(DATA/'admin-secret').read_text().strip().encode()):
                FAILURES[ip]=attempts+[now]; return self.send(401,{'error':'密码不正确'})
            FAILURES.pop(ip,None)
            token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(24)
            SESSIONS[token]={'csrf':csrf,'expires':now+43200}
            # Cap anonymous/state memory usage.
            for key,value in list(SESSIONS.items()):
                if value['expires']<now: SESSIONS.pop(key,None)
            return self.send(200,{'csrf':csrf},cookie='session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+('; Secure' if SETTINGS.panel_origin.startswith('https://') else ''))
        s=self.session()
        if not s: return self.send(401,{'error':'请登录'})
        if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']): return self.send(403,{'error':'请求验证失败'})
        if self.path=='/api/settings':
            with LOCK:
                try: result=save_preferences(DATA,body,atomic)
                except ValueError as e: return self.send(400,{'error':str(e)})
            return self.send(200,{'ok':True,'preferences':result})
        if self.path=='/api/password':
            current=body.get('current_password');new=body.get('new_password');confirm=body.get('confirm_password')
            if not all(isinstance(x,str) for x in (current,new,confirm)):
                return self.send(400,{'error':'密码参数无效'})
            if not 16<=len(new)<=256 or new!=new.strip(): return self.send(400,{'error':'新密码需要 16–256 个字符，首尾不能有空格'})
            if new!=confirm: return self.send(400,{'error':'两次输入的新密码不一致'})
            with LOCK:
                ip=self.client_address[0];now=time.time()
                attempts=[t for t in FAILURES.get(ip,[]) if now-t<300]
                if len(attempts)>=8: return self.send(429,{'error':'尝试过多，请五分钟后再试'})
                if not hmac.compare_digest(current.encode(),(DATA/'admin-secret').read_text().strip().encode()):
                    FAILURES[ip]=attempts+[now];return self.send(403,{'error':'当前密码不正确'})
                if hmac.compare_digest(new.encode(),(ROOT/'secret').read_text().strip().encode()):
                    return self.send(400,{'error':'管理密码不能与核心密钥相同'})
                atomic(DATA/'admin-secret',new+'\n')
                SESSIONS.clear();FAILURES.pop(ip,None)
            return self.send(200,{'ok':True,'reauthenticate':True},cookie='session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')
        if self.path=='/api/logout':
            c=http.cookies.SimpleCookie(self.headers.get('Cookie','')); SESSIONS.pop(c['session'].value,None)
            return self.send(200,{'ok':True},cookie='session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')
        if self.path=='/api/subscriptions':
            with LOCK:
                registry=Subscriptions(DATA,atomic,SETTINGS.provider)
                try:
                    action=body.get('action')
                    if action=='add': registry.add(body.get('name'),body.get('url'))
                    elif action=='remove': registry.remove(body.get('id'))
                    elif action=='switch': registry.switch(body.get('id'),subscription_apply)
                    elif action=='refresh':
                        core('/providers/proxies/'+quote(SETTINGS.provider,safe=''),'PUT');subscription_apply()
                    else: raise ValueError('未知订阅操作')
                except ValueError as e: return self.send(400,{'error':str(e)})
                except RuntimeError as e: return self.send(503,{'error':str(e)})
                except Exception: return self.send(503,{'error':'订阅操作失败，请检查链接或核心连接'})
            return self.send(200,{'ok':True})
        if self.path=='/api/device':
            mac=body.get('mac',''); enabled=body.get('enabled'); name=body.get('name')
            if not isinstance(mac,str) or not MAC.fullmatch(mac) or (enabled is not None and type(enabled) is not bool) or (name is not None and (not isinstance(name,str) or len(name)>60)):
                return self.send(400,{'error':'设备参数无效'})
            with LOCK:
                devices=load(); d=devices.get(mac)
                if not d: return self.send(404,{'error':'设备尚未发现'})
                if enabled is not None and not valid_ip(d.get('ip')): return self.send(409,{'error':'设备暂无有效地址，请重新连接 Wi-Fi'})
                old=copy.deepcopy(devices)
                if enabled is not None: d['enabled']=enabled
                if name is not None: d['name']=name.strip()
                try:
                    apply(devices); save(devices)
                except Exception:
                    try: apply(old,True); save(old)
                    except Exception: pass
                    return self.send(503,{'error':'规则未成功生效，已尝试恢复原设置'})
                failures=0
                if enabled is not None:
                    try: failures=close_connections(d['ip'])
                    except Exception: failures=1
                return self.send(200,{'ok':True,'warning':'规则已生效，部分旧连接请手动重开' if failures else ''})
        return self.send(404,{'error':'不存在'})

if __name__=='__main__':
    DATA.mkdir(parents=True,exist_ok=True)
    if not (DATA/'settings.json').exists() or not (DATA/'admin-secret').exists():
        raise SystemExit('Run scripts/initialize.py before starting the controller')
    for path in (DATA/'admin-secret',ROOT/'secret'):
        if len(path.read_text().strip())<16:raise SystemExit('Set separate strong panel and core credentials')
    DEVICE_TRAFFIC=DeviceTraffic(DATA/'device-traffic.json',atomic)
    atexit.register(DEVICE_TRAFFIC.flush)
    def shutdown(signum,frame):
        DEVICE_TRAFFIC.flush();raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown)
    threading.Thread(target=collect_stats,daemon=True).start()
    threading.Thread(target=discovery,daemon=True).start()
    threading.Thread(target=router_names,daemon=True).start()
    threading.Thread(target=dhcp_supervisor,daemon=True).start()
    ThreadingHTTPServer((SETTINGS.bind,SETTINGS.panel_port),Handler).serve_forever()
