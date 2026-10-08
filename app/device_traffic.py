"""Observed proxy bytes by MAC; polling is an estimate, not provider billing.

First snapshot baselines existing connections. Persist totals and active offsets
in the same atomic checkpoint to prevent double counting after a restart.
"""
import copy, json, threading, time
from pathlib import Path

PROXY_TYPES=frozenset(('Shadowsocks','ShadowsocksR','Snell','Socks5','Http','Vmess','Vless','Trojan','Hysteria','Hysteria2','WireGuard','Tuic','Ssh','Mieru','AnyTLS','Sudoku','Masque','TrustTunnel','ShadowQuic','OpenVPN','Tailscale','ZeroTier','EasyTier','GostRelay'))

def proxy_nodes(proxies,providers=None):
    result={name for name,value in proxies.items() if value.get('type') in PROXY_TYPES}
    # Provider-backed nodes are absent from /proxies on some Mihomo versions.
    for provider in (providers or {}).values():
        result.update(p['name'] for p in provider.get('proxies',[]) if isinstance(p.get('name'),str) and p.get('type') in PROXY_TYPES)
    return result

def ip_owners(devices):
    # Ambiguous/stale duplicate addresses must not assign bytes to the wrong MAC.
    candidates={}
    for mac,d in devices.items():
        if d.get('ip'): candidates.setdefault(d['ip'],set()).add(mac)
    return {ip:next(iter(macs)) for ip,macs in candidates.items() if len(macs)==1}

class DeviceTraffic:
    def __init__(self,path=None,writer=None):
        self.lock=threading.Lock();self.path=Path(path) if path else None;self.writer=writer
        self.totals={};self.active={};self.since=int(time.time());self.updated=0;self.last_saved=0;self.baseline=True;self.error=''
        if self.path and self.path.exists():
            try:
                saved=json.loads(self.path.read_text())
                if saved.get('version')!=1:raise ValueError('Unsupported traffic format')
                self.totals=saved['totals'];self.active=saved['active'];self.since=saved['since']
            except (OSError,ValueError,KeyError,TypeError):
                # Preserve an unreadable ledger for recovery, rather than overwriting it.
                self.error='设备流量记录无法读取'
    def sample(self,connections,owners,nodes,now=None):
        now=time.time() if now is None else now
        with self.lock:
            if self.error:return
            current={}
            for c in connections:
                key=c.get('id');chain=c.get('chains') or []
                if not isinstance(key,str) or not chain or chain[0] not in nodes:continue
                previous=self.active.get(key)
                mac=previous['mac'] if previous else owners.get(c.get('metadata',{}).get('sourceIP'))
                # If ownership is discovered later, start baselining then.
                if not mac:continue
                def counter(k):
                    value=c.get(k,0)
                    return max(0,int(value)) if isinstance(value,(int,float)) else 0
                up=counter('upload');down=counter('download')
                if previous:
                    delta_up=max(0,up-previous['upload']);delta_down=max(0,down-previous['download'])
                elif self.baseline:
                    delta_up=delta_down=0
                else:
                    delta_up=up;delta_down=down
                item=self.totals.setdefault(mac,{'upload':0,'download':0})
                item['upload']+=delta_up;item['download']+=delta_down
                current[key]={'mac':mac,'upload':up,'download':down}
            self.active=current;self.baseline=False;self.updated=now
            if self.path and self.writer and now-self.last_saved>=30:self._save(now)
    def _save(self,now):
        self.writer(self.path,json.dumps({'version':1,'since':self.since,'totals':self.totals,'active':self.active},ensure_ascii=False))
        self.last_saved=now
    def flush(self):
        with self.lock:
            if self.path and self.writer and not self.error:self._save(time.time())
    def snapshot(self):
        with self.lock:
            totals=copy.deepcopy(self.totals)
            for d in totals.values():d['total']=d['upload']+d['download']
            return {'devices':totals,'since':self.since,'updated':self.updated,'ok':not self.error and bool(self.updated) and time.time()-self.updated<8,'error':self.error}
