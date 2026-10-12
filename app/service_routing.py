"""Destination routing within the existing per-device smart-routing whitelist."""
import copy
import hashlib
import json
from pathlib import Path

OPENAI_PROVIDER = 'ndf-openai'
OPENAI_GROUP = 'NDF-OPENAI'
OPENAI_PREFIX = 'OpenAI | '
# First-party domains from OpenAI's network recommendations. Shared third-party
# domains stay with the default subscription; this is destination, not process routing.
OPENAI_DOMAINS = ('openai.com', 'chatgpt.com', 'oaistatic.com', 'oaiusercontent.com', 'oaistatsig.com')
OPENAI_EXACT = ('cdn.openaimerge.com',)


def read_registry(directory):
    path = Path(directory) / 'subscriptions.json'
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('订阅配置无效')
    return value


def binding_id(registry):
    value = registry.get('openai_subscription', '')
    if not isinstance(value, str):
        raise ValueError('OpenAI 订阅设置无效')
    return value


def compile_openai(base, registry, provider='subscription'):
    result = copy.deepcopy(base)
    identifier = binding_id(registry)
    if not identifier:
        return result
    item = next((x for x in registry.get('items', []) if x.get('id') == identifier), None)
    if not item:
        raise ValueError('OpenAI 专用订阅不存在')
    if OPENAI_PROVIDER in result.get('proxy-providers', {}) or any(
            g.get('name') == OPENAI_GROUP for g in result.get('proxy-groups', [])):
        raise ValueError('OpenAI 分流名称与现有配置冲突')
    source = copy.deepcopy(result['proxy-providers'][provider])
    source['url'] = item['url']
    source['path'] = './providers/openai-' + hashlib.sha256(item['url'].encode()).hexdigest()[:16] + '.yaml'
    override = source.setdefault('override', {})
    override['additional-prefix'] = OPENAI_PREFIX + override.get('additional-prefix', '')
    result['proxy-providers'][OPENAI_PROVIDER] = source
    result.setdefault('proxy-groups', []).append({
        'name': OPENAI_GROUP, 'type': 'fallback', 'use': [OPENAI_PROVIDER],
        'url': 'https://www.gstatic.com/generate_204', 'interval': 300,
        'empty-fallback': 'REJECT',
        'exclude-type': 'DIRECT|REJECT|PASS|COMPATIBLE|DNS',
    })
    specific = ['DOMAIN-SUFFIX,' + domain + ',' + OPENAI_GROUP for domain in OPENAI_DOMAINS]
    specific += ['DOMAIN,' + domain + ',' + OPENAI_GROUP for domain in OPENAI_EXACT]
    result['rules'] = specific + result['rules']
    return result


def validate_openai_core(core, registry):
    if not binding_id(registry):
        return
    nodes = core('/providers/proxies/' + OPENAI_PROVIDER).get('proxies') or []
    group = core('/proxies/' + OPENAI_GROUP)
    names = {x.get('name') for x in nodes}
    if not names or group.get('now') not in names:
        raise RuntimeError('OpenAI 专用订阅未加载可用节点')
    selected=next(x for x in nodes if x.get('name')==group['now'])
    if str(selected.get('type','')).casefold() in {'direct','reject','pass','compatible','dns'}:
        raise RuntimeError('OpenAI 专用订阅未加载可用节点')
