"""User-facing preferences, separate from deployment/network configuration."""
import json


def load_preferences(directory):
    path = directory / 'preferences.json'
    if not path.exists():
        return {'new_device_proxy': False}
    value = json.loads(path.read_text())
    if type(value.get('new_device_proxy')) is not bool:
        raise ValueError('Invalid new-device preference')
    return {'new_device_proxy': value['new_device_proxy']}


def save_preferences(directory, value, writer):
    if set(value) != {'new_device_proxy'} or type(value['new_device_proxy']) is not bool:
        raise ValueError('设置参数无效')
    writer(directory / 'preferences.json', json.dumps(value) + '\n')
    return dict(value)
