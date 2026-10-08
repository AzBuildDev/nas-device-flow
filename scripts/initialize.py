#!/usr/bin/env python3
"""Generate private state without starting networking or DHCP."""
import argparse,fcntl,getpass,ipaddress,json,os,re,secrets,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import yaml
from settings import Settings
from subscriptions import validate_url

def private_write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(text)

def core_base(settings,secret,url):
    return {'mixed-port':7890,'allow-lan':True,'lan-allowed-ips':[settings.subnet],'bind-address':'*','mode':'rule','log-level':'warning','ipv6':False,'external-controller':f'0.0.0.0:{settings.core_port}','secret':secret,
      'tun':{'enable':True,'stack':'gvisor','auto-route':True,'auto-redirect':True,'strict-route':True,'dns-hijack':['any:53']},
      'dns':{'enable':True,'listen':'0.0.0.0:53','ipv6':False,'enhanced-mode':'fake-ip','fake-ip-range':'198.18.0.1/16','nameserver':settings.direct_dns,'default-nameserver':['223.5.5.5','119.29.29.29']},
      'proxy-providers':{settings.provider:{'type':'http','url':url,'path':'./providers/subscription.yaml','interval':43200,'size-limit':5242880,'health-check':{'enable':True,'url':'https://www.gstatic.com/generate_204','interval':300}}},
      'proxy-groups':[{'name':settings.proxy_group,'type':'select','proxies':[settings.auto_group],'use':[settings.provider]},{'name':settings.auto_group,'type':'fallback','use':[settings.provider],'url':'https://www.gstatic.com/generate_204','interval':300}],
      'rules':['GEOSITE,cn,DIRECT','GEOIP,cn,DIRECT','MATCH,'+settings.proxy_group]}

def validate_fixed_hosts(settings, text):
    seen_macs=set();seen_ips=set()
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):continue
        fields=line.split(',')
        if len(fields)!=4 or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',fields[0]) or fields[1]!='set:infrastructure' or fields[3]!='infinite':
            raise ValueError('Fixed hosts use MAC,set:infrastructure,IP,infinite')
        if fields[2] not in settings.infrastructure or fields[0].lower() in seen_macs or fields[2] in seen_ips:
            raise ValueError('Fixed hosts must use distinct configured infrastructure addresses')
        seen_macs.add(fields[0].lower());seen_ips.add(fields[2])
    return text

def initialize(project,config,admin_password,url,fixed_hosts=''):
    settings=Settings(**config);validate_url(url);validate_fixed_hosts(settings,fixed_hosts)
    if not 16<=len(admin_password)<=256 or admin_password!=admin_password.strip():raise ValueError('Use 16 to 256 characters without leading/trailing spaces for the panel password')
    project=Path(project);runtime=project/'runtime';data=runtime/'control-center'
    if runtime.exists():raise ValueError('runtime already exists; never overwrite an existing deployment')
    # Compose creates macvlan interfaces named eth0; choose pool/settings before bootstrap.
    if settings.interface!='eth0':raise ValueError('Compose container interface is eth0; parent interface is configured separately')
    runtime.mkdir(mode=0o700);data.mkdir(mode=0o700)
    core_secret=secrets.token_urlsafe(32);base=core_base(settings,core_secret,url)
    private_write(runtime/'secret',core_secret+'\n');private_write(data/'admin-secret',admin_password+'\n')
    private_write(data/'settings.json',json.dumps(config,indent=2)+'\n')
    private_write(data/'base.yaml',yaml.safe_dump(base,allow_unicode=True,sort_keys=False))
    # Default all devices DIRECT, preserving domestic/foreign rules in a sub-rule.
    running=dict(base);running['sub-rules']={'smart-routing':base['rules']};running['rules']=['MATCH,DIRECT']
    private_write(runtime/'config.yaml',yaml.safe_dump(running,allow_unicode=True,sort_keys=False))
    private_write(data/'devices.json','{}\n');private_write(data/'router-adapter.json','{"type":"none"}\n')
    private_write(data/'dnsmasq.conf',settings.dnsmasq(Path('/data/control-center')))
    private_write(data/'fixed.hosts',fixed_hosts);private_write(data/'dhcp.hosts',fixed_hosts)
    return settings

def bootstrap(project,config,admin_password,url,parent,fixed_hosts='',deployment=None):
    """Commit validated private state; serialize installers and never replace state."""
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}',parent):raise ValueError('Invalid parent interface')
    project=Path(project)
    lock_fd=os.open(project/'.ndf-install.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(lock_fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if any(os.path.lexists(project/name) for name in ('.env','runtime','deployment.compose.yaml')):
            raise ValueError('Existing .env/runtime found; bootstrap refuses to overwrite')
        with tempfile.TemporaryDirectory(prefix='.ndf-install-',dir=project) as tmp:
            staged=Path(tmp)
            settings=initialize(staged,config,admin_password,url,fixed_hosts)
            env=f'LAN_SUBNET={settings.subnet}\nUPSTREAM_GATEWAY={settings.upstream}\nPARENT_INTERFACE={parent}\nCORE_IP={settings.core_ip}\nPANEL_IP={settings.panel_ip}\n'
            private_write(staged/'.env',env)
            if deployment is not None:private_write(staged/'deployment.compose.yaml',deployment)
            # O_EXCL-equivalent hard link prevents replacing an independently created .env.
            os.link(staged/'.env',project/'.env')
            linked=False
            try:
                if deployment is not None:
                    os.link(staged/'deployment.compose.yaml',project/'deployment.compose.yaml');linked=True
                if os.path.lexists(project/'runtime'):raise ValueError('runtime appeared during installation')
                (staged/'runtime').rename(project/'runtime')
            except BaseException:
                (project/'.env').unlink()
                if linked:(project/'deployment.compose.yaml').unlink()
                raise
            return settings

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--settings',type=Path,default=Path('examples/settings.json'));p.add_argument('--parent',required=True);p.add_argument('--fixed-hosts',type=Path);a=p.parse_args()
    if not __import__('re').fullmatch(r'[A-Za-z0-9_.:-]{1,32}',a.parent):raise SystemExit('Invalid parent interface')
    project=Path.cwd()
    if (project/'.env').exists() or (project/'runtime').exists():raise SystemExit('Existing .env/runtime found; bootstrap refuses to overwrite')
    config=json.loads(a.settings.read_text());Settings(**config)
    password=getpass.getpass('New panel password (16+ characters): ')
    if password!=getpass.getpass('Confirm panel password: '):raise SystemExit('Passwords differ')
    url=getpass.getpass('Clash/Mihomo subscription URL (hidden): ')
    bootstrap(project,config,password,url,a.parent,a.fixed_hosts.read_text() if a.fixed_hosts else '')
    print('Private runtime created. DHCP is OFF. Review docs/installation.md before docker compose up.')
if __name__=='__main__':main()
