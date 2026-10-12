import copy
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from service_routing import compile_openai, read_registry, validate_openai_core, OPENAI_GROUP, OPENAI_PROVIDER
from subscriptions import Subscriptions
from test_controller import c

BASE = {'proxy-providers': {'subscription': {'type': 'http', 'url': 'https://example.invalid/bangkok.yaml',
         'path': './providers/main.yaml', 'override': {'skip-cert-verify': False}}},
        'proxy-groups': [{'name': 'PROXY', 'type': 'select', 'use': ['subscription']}],
        'rules': ['GEOSITE,cn,DIRECT', 'GEOIP,cn,DIRECT', 'MATCH,PROXY'], 'dns': {'nameserver': ['old']}}
REGISTRY = {'active': 'bangkok-demo', 'openai_subscription': 'us-demo', 'items': [
    {'id': 'us-demo', 'name': 'US demo', 'url': 'https://example.invalid/us.yaml', 'created': 1},
    {'id': 'bangkok-demo', 'name': 'Bangkok demo', 'url': 'https://example.invalid/bangkok.yaml', 'created': 1}]}


class RoutingTests(unittest.TestCase):
    def test_two_independent_providers_and_first_party_priority(self):
        original = copy.deepcopy(BASE)
        result = compile_openai(BASE, REGISTRY)
        self.assertEqual(BASE, original)
        self.assertEqual(result['proxy-providers']['subscription']['url'], original['proxy-providers']['subscription']['url'])
        provider = result['proxy-providers'][OPENAI_PROVIDER]
        self.assertEqual(provider['url'], REGISTRY['items'][0]['url'])
        self.assertNotEqual(provider['path'], result['proxy-providers']['subscription']['path'])
        self.assertFalse(provider['override']['skip-cert-verify'])
        self.assertIn('additional-prefix', provider['override'])
        self.assertLess(result['rules'].index('DOMAIN-SUFFIX,chatgpt.com,' + OPENAI_GROUP), result['rules'].index('GEOSITE,cn,DIRECT'))
        self.assertEqual(result['rules'][-1], 'MATCH,PROXY')
        group = result['proxy-groups'][-1]
        self.assertEqual(group['use'], [OPENAI_PROVIDER])
        self.assertEqual(group['empty-fallback'], 'REJECT')
        self.assertNotIn('subscription', group['use'])

    def test_default_subscription_changes_do_not_replace_openai(self):
        alternate = copy.deepcopy(BASE)
        alternate['proxy-providers']['subscription']['url'] = 'https://example.invalid/other.yaml'
        self.assertEqual(compile_openai(alternate, REGISTRY)['proxy-providers'][OPENAI_PROVIDER]['url'], REGISTRY['items'][0]['url'])

    def test_disabled_binding_preserves_old_configuration(self):
        self.assertEqual(compile_openai(BASE, {}), BASE)
        self.assertEqual(compile_openai(BASE, dict(REGISTRY, openai_subscription='')), BASE)

    def test_device_whitelist_still_controls_openai_and_disabled_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'subscriptions.json').write_text(json.dumps(REGISTRY))
            with patch.object(c, 'DATA', directory), patch.object(c, 'SETTINGS', c.Settings()):
                result = c.render(BASE, {
                    'on': {'enabled': True, 'ip': '192.168.50.181'},
                    'off': {'enabled': False, 'ip': '192.168.50.182'},
                    'router': {'enabled': True, 'ip': '192.168.50.1'}})
            self.assertEqual(result['rules'], ['SUB-RULE,(SRC-IP-CIDR,192.168.50.181/32),smart-routing', 'MATCH,DIRECT'])
            self.assertIn('DOMAIN-SUFFIX,openai.com,' + OPENAI_GROUP, result['sub-rules']['smart-routing'])

    def test_invalid_or_conflicting_bindings_fail_without_mutating_base(self):
        for registry in (dict(REGISTRY, openai_subscription='missing'), dict(REGISTRY, openai_subscription=True)):
            with self.assertRaises(ValueError):
                compile_openai(BASE, registry)
        conflict = copy.deepcopy(BASE)
        conflict['proxy-groups'].append({'name': OPENAI_GROUP})
        with self.assertRaises(ValueError):
            compile_openai(conflict, REGISTRY)

    def test_loaded_group_must_select_a_node_from_its_provider(self):
        for selected in ('REJECT', 'DIRECT', 'Bangkok demo'):
            with self.assertRaises(RuntimeError):
                validate_openai_core(lambda path: {'proxies': [{'name': 'US demo'}]} if '/providers/' in path else {'now': selected}, REGISTRY)
        validate_openai_core(lambda path: {'proxies': [{'name': 'US demo'}]} if '/providers/' in path else {'now': 'US demo'}, REGISTRY)
    def test_direct_node_is_not_accepted_as_an_openai_proxy(self):
        with self.assertRaises(RuntimeError):
            validate_openai_core(lambda path: {'proxies':[{'name':'US demo','type':'Direct'}]} if '/providers/' in path else {'now':'US demo'},REGISTRY)

    def test_malformed_private_registry_does_not_silently_disable_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'subscriptions.json').write_text('[]')
            with self.assertRaises(ValueError):
                read_registry(tmp)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        (self.directory / 'base.yaml').write_text('unchanged')
        (self.directory / 'subscriptions.json').write_text(json.dumps(dict(REGISTRY, openai_subscription='')))
        self.registry = Subscriptions(self.directory, lambda path, text: path.write_text(text))

    def test_setting_binding_persists_and_keeps_default_and_base(self):
        seen = []
        self.registry.set_openai('us-demo', lambda: seen.append(self.registry.load()['openai_subscription']))
        self.assertEqual(seen, ['us-demo'])
        self.assertEqual(self.registry.load()['active'], 'bangkok-demo')
        self.assertEqual((self.directory / 'base.yaml').read_text(), 'unchanged')
        self.assertNotIn('us.yaml', json.dumps(self.registry.summaries()))
        self.registry.set_openai('', lambda: None)
        self.assertEqual(self.registry.summaries()['openai_subscription'], '')

    def test_referenced_subscription_cannot_be_deleted(self):
        self.registry.set_openai('us-demo', lambda: None)
        with self.assertRaises(ValueError):
            self.registry.remove('us-demo')
        self.registry.set_openai('', lambda: None)
        self.registry.remove('us-demo')
        self.assertEqual(len(self.registry.load()['items']), 1)

    def test_apply_failure_restores_old_binding_and_configuration(self):
        before = self.registry.load()
        calls = []
        def apply():
            calls.append(self.registry.load().get('openai_subscription', ''))
            if len(calls) == 1:
                raise RuntimeError('sensitive details must not escape')
        with self.assertRaisesRegex(RuntimeError, '已恢复') as error:
            self.registry.set_openai('us-demo', apply)
        self.assertNotIn('sensitive', str(error.exception))
        self.assertEqual(calls, ['us-demo', ''])
        self.assertEqual(self.registry.load(), before)

    def test_unknown_binding_does_not_apply_or_write(self):
        before = self.registry.load()
        with self.assertRaises(ValueError):
            self.registry.set_openai('missing', lambda: self.fail('unexpected apply'))
        self.assertEqual(self.registry.load(), before)


if __name__ == '__main__':
    unittest.main()
