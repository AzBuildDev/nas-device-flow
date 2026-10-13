"""Conservative summaries of provider loading, recent checks and account metadata."""
from datetime import datetime, timezone
import math,time

NON_PROXY={'direct','reject','pass','compatible','dns'}

def number(value):
    return value if type(value) in (int,float) and math.isfinite(value) else None

def checked_time(value):
    if not isinstance(value,str):return 0
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        return dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()
    except (ValueError,OverflowError):return 0

def node_check(node,test_url,now):
    extra=node.get('extra') or {}
    record=extra.get(test_url) if isinstance(extra,dict) else None
    record=record if isinstance(record,dict) else node
    history=record.get('history') or []
    if not isinstance(history,list) or not history or not isinstance(history[-1],dict):return ('untested',0,None)
    last=history[-1];stamp=checked_time(last.get('time'));delay=number(last.get('delay'))
    if not stamp or stamp>now+60 or delay is None:return ('untested',0,None)
    if now-stamp>600:return ('stale',stamp,None)
    if delay<=0 or record.get('alive') is False:return ('failed',stamp,None)
    return ('healthy',stamp,delay)

def provider_status(provider,selected,now=None):
    now=time.time() if now is None else now
    result={'state':'unavailable','checked_at':0,'delay_ms':None,'node_count':0,'tested_count':0,'healthy_count':0,'account':'unknown','remaining':None,'expires_at':None}
    if not isinstance(provider,dict):return result
    raw=provider.get('proxies') or []
    nodes=[n for n in raw if isinstance(n,dict)] if isinstance(raw,list) else []
    result['node_count']=len(nodes)
    checks={n.get('name'):node_check(n,provider.get('testUrl',''),now) for n in nodes}
    result['tested_count']=sum(c[0] in ('healthy','failed') for c in checks.values())
    result['healthy_count']=sum(c[0]=='healthy' for c in checks.values())
    current=next((n for n in nodes if n.get('name')==selected),None)
    if not nodes:result['state']='unloaded'
    elif str(selected).casefold() in NON_PROXY or (current and str(current.get('type','')).casefold() in NON_PROXY):result['state']='direct'
    elif current is None:result['state']='not_selected'
    else:result['state'],result['checked_at'],result['delay_ms']=checks[selected]
    usage=provider.get('subscriptionInfo')
    if isinstance(usage,dict):
        total=number(usage.get('Total'));expiry=number(usage.get('Expire'));up=number(usage.get('Upload'));down=number(usage.get('Download'))
        if expiry and expiry>0:result['expires_at']=expiry
        if total and total>0 and up is not None and down is not None:
            result['remaining']=max(0,total-max(0,up)-max(0,down))
        if expiry and 0<expiry<=now:result['account']='expired'
        elif result['remaining']==0:result['account']='exhausted'
        elif result['remaining'] is not None or result['expires_at']:result['account']='normal'
    return result
