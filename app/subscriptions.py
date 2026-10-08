"""Private subscription registry. URLs are never included in public summaries."""
import copy,hashlib,json,secrets,time
from urllib.parse import urlsplit
import yaml

def validate_url(value):
    if not isinstance(value,str) or len(value)>2048: raise ValueError('订阅链接过长')
    u=urlsplit(value)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.fragment:
        raise ValueError('请输入 HTTP/HTTPS 订阅链接，不支持链接中的登录凭据')
    return value

class Subscriptions:
    def __init__(self,directory,atomic,provider='subscription'):self.directory=directory;self.atomic=atomic;self.provider=provider
    def load(self):
        p=self.directory/'subscriptions.json'
        if p.exists():return json.loads(p.read_text())
        base=yaml.safe_load((self.directory/'base.yaml').read_text())
        value={'active':'original','items':[{'id':'original','name':'当前订阅','url':base['proxy-providers'][self.provider]['url'],'created':int(time.time())}]}
        self.save(value);return value
    def save(self,value):self.atomic(self.directory/'subscriptions.json',json.dumps(value,ensure_ascii=False,indent=2))
    def summaries(self):
        value=self.load()
        return {'active':value['active'],'items':[{'id':x['id'],'name':x['name'],'host':urlsplit(x['url']).hostname,'created':x['created']} for x in value['items']]}
    def add(self,name,url):
        if not isinstance(name,str) or not 1<=len(name.strip())<=60:raise ValueError('名称需要 1–60 个字符')
        validate_url(url);value=self.load()
        if len(value['items'])>=20:raise ValueError('最多保存 20 个订阅')
        if any(x['url']==url for x in value['items']):raise ValueError('这个订阅已经保存')
        value['items'].append({'id':secrets.token_hex(8),'name':name.strip(),'url':url,'created':int(time.time())});self.save(value)
    def remove(self,identifier):
        value=self.load()
        if identifier==value['active']:raise ValueError('请先切换到其他订阅，再删除当前订阅')
        if not any(x['id']==identifier for x in value['items']):raise ValueError('订阅不存在')
        value['items']=[x for x in value['items'] if x['id']!=identifier];self.save(value)
    def switch(self,identifier,apply):
        value=self.load();item=next((x for x in value['items'] if x['id']==identifier),None)
        if not item:raise ValueError('订阅不存在')
        path=self.directory/'base.yaml';old=path.read_text();base=yaml.safe_load(old)
        provider=base['proxy-providers'][self.provider];provider['url']=item['url']
        # A separate cache prevents accidentally accepting nodes from the previous subscription.
        if identifier!=value['active']:provider['path']='./providers/sub-'+hashlib.sha256(item['url'].encode()).hexdigest()[:16]+'.yaml'
        try:
            self.atomic(path,yaml.safe_dump(base,allow_unicode=True,sort_keys=False));apply()
            value['active']=identifier;self.save(value)
        except Exception:
            self.atomic(path,old)
            try:apply()
            except Exception:raise RuntimeError('切换失败，原订阅恢复未确认，请检查核心状态') from None
            raise RuntimeError('切换失败，已恢复原订阅；请检查链接、格式或网络') from None
