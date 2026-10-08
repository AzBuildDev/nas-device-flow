"""Validated deployment settings; private runtime configuration lives outside source."""
import ipaddress,json,os,re
from dataclasses import dataclass,field
from pathlib import Path
from urllib.parse import urlsplit

@dataclass
class Settings:
    subnet:str='192.168.50.0/24'
    upstream:str='192.168.50.1'
    core_ip:str='192.168.50.250'
    panel_ip:str='192.168.50.254'
    infrastructure:list=field(default_factory=list)
    interface:str='eth0'
    core_port:int=9090
    panel_port:int=9080
    panel_origin:str='http://192.168.50.254:9080'
    bind:str='0.0.0.0'
    provider:str='subscription'
    proxy_group:str='PROXY'
    auto_group:str='AUTO'
    core_config_path:str='/root/.config/mihomo/config.yaml'
    dhcp_authoritative:bool=False
    dhcp_start:str='192.168.50.180'
    dhcp_end:str='192.168.50.249'
    direct_dns:list=field(default_factory=lambda:['https://dns.alidns.com/dns-query','https://doh.pub/dns-query'])
    def __post_init__(self):
        self.network=ipaddress.ip_network(self.subnet,strict=True)
        if self.network.version!=4 or not self.network.is_private or not 22<=self.network.prefixlen<=29: raise ValueError('Use a private IPv4 subnet with /22 to /29 prefix')
        for key in ('upstream','core_ip','panel_ip','dhcp_start','dhcp_end'):
            value=str(ipaddress.IPv4Address(getattr(self,key)))
            if ipaddress.ip_address(value) not in self.network or value in (str(self.network.network_address),str(self.network.broadcast_address)):raise ValueError('Network addresses must be usable hosts in subnet')
            setattr(self,key,value)
        if len({self.upstream,self.core_ip,self.panel_ip})!=3:raise ValueError('Gateway, core and panel need distinct addresses')
        self.infrastructure=[str(ipaddress.IPv4Address(x)) for x in self.infrastructure]
        if any(ipaddress.ip_address(x) not in self.network for x in self.infrastructure):raise ValueError('Infrastructure must be in subnet')
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}',self.interface):raise ValueError('Invalid interface')
        for port in (self.core_port,self.panel_port):
            if type(port)!=int or not 1<=port<=65535:raise ValueError('Invalid port')
        origin=urlsplit(self.panel_origin)
        if origin.scheme not in ('http','https') or not origin.hostname or origin.path not in ('','/') or origin.username or origin.password or origin.query or origin.fragment:raise ValueError('Invalid panel origin')
        self.panel_origin=self.panel_origin.rstrip('/')
        if type(self.dhcp_authoritative) is not bool:raise ValueError('dhcp_authoritative must be boolean')
        if int(ipaddress.ip_address(self.dhcp_start))>int(ipaddress.ip_address(self.dhcp_end)):raise ValueError('Invalid DHCP pool')
        if any(int(ipaddress.ip_address(self.dhcp_start))<=int(ipaddress.ip_address(x))<=int(ipaddress.ip_address(self.dhcp_end)) for x in self.excluded):raise ValueError('Infrastructure addresses must be outside DHCP pool')
        if not self.direct_dns or any(not isinstance(x,str) or not x.startswith('https://') for x in self.direct_dns):raise ValueError('Use HTTPS direct DNS resolvers')
        for name in (self.provider,self.proxy_group,self.auto_group):
            if not isinstance(name,str) or not 1<=len(name)<=80:raise ValueError('Invalid core group/provider name')
    @property
    def excluded(self):return set(self.infrastructure+[self.upstream,self.core_ip,self.panel_ip])
    @property
    def core_url(self):return 'http://'+self.core_ip+':'+str(self.core_port)
    def valid_ip(self,value):
        try:return isinstance(value,str) and ipaddress.ip_address(value) in self.network and value not in self.excluded and value not in (str(self.network.network_address),str(self.network.broadcast_address))
        except ValueError:return False
    def scan_hosts(self):return [str(ip) for ip in self.network.hosts() if str(ip) not in self.excluded]
    def dnsmasq(self,data_dir):
        p=Path(data_dir)
        if any(c in str(p) for c in ('\n','\r',',')):raise ValueError('Invalid data path')
        lines=['port=0','interface='+self.interface,'bind-dynamic','no-resolv','no-hosts','user=root',f'dhcp-range={self.dhcp_start},{self.dhcp_end},{self.network.netmask},12h','dhcp-option=option:router,'+self.core_ip,'dhcp-option=option:dns-server,'+self.core_ip,'dhcp-option=tag:infrastructure,option:router,'+self.upstream,'dhcp-option=tag:infrastructure,option:dns-server,'+self.upstream,'dhcp-hostsfile='+str(p/'dhcp.hosts'),'dhcp-leasefile='+str(p/'dnsmasq.leases'),'log-facility=-']
        if self.dhcp_authoritative:lines.append('dhcp-authoritative')
        return '\n'.join(lines)+'\n'
    @classmethod
    def load(cls,path):
        return cls(**json.loads(Path(path).read_text())) if Path(path).exists() else cls()
