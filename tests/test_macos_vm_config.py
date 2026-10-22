"""Boundaries for read-only validation and explicit Lima config generation."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('macos_vm_config', ROOT / 'scripts/macos/vm-config.py')
vm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vm)


class MacOSVMConfigTests(unittest.TestCase):
    def setUp(self):
        # Unix socket names are short on macOS; avoid long repository-based paths.
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-vm-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.socket_path = self.root / 'bridge.sock'
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(str(self.socket_path))
        self.addCleanup(self.socket.close)

    def config(self, **kwargs):
        return vm.make_config(str(self.socket_path), str(ROOT), **kwargs)

    def test_generates_source_only_vm_without_lan_addresses(self):
        config = self.config(architecture='arm64')
        self.assertEqual(config['base'], 'template:_images/ubuntu-lts')
        self.assertNotIn('provision', config)
        self.assertEqual(config['vmType'], 'vz')
        self.assertEqual(config['arch'], 'aarch64')
        self.assertEqual(config['containerd'], {'system': False, 'user': False})
        self.assertEqual(config['networks'], [{'socket': str(self.socket_path), 'interface': 'ndflan', 'metric': 50}])
        self.assertEqual(config['mounts'], [{'location': str(ROOT), 'mountPoint': '/mnt/ndf-source', 'writable': False}])
        self.assertNotIn('192.168.', json.dumps(config))
        self.assertNotIn('proxies', config)

    def test_rejects_missing_file_or_directory_instead_of_socket(self):
        regular = self.root / 'file'; regular.write_text('not a socket')
        for path in [self.root / 'missing', regular, self.root]:
            with self.assertRaises(ValueError):
                vm.make_config(str(path), str(ROOT))

    def test_rejects_path_template_injection_controls_and_relative_paths(self):
        for path in ['relative.sock', '/tmp/socket\nvmType: qemu', '/tmp/{{.Home}}/socket', '/tmp/socket\x00suffix']:
            with self.assertRaises(ValueError):
                vm.make_config(path, str(ROOT))
        with self.assertRaises(ValueError):
            vm.make_config(str(self.socket_path), str(self.root))
        with self.assertRaises(ValueError):
            vm.make_config(str(self.socket_path), str(ROOT), 'riscv64')

    def test_exclusive_output_preserves_files_and_symlinks(self):
        config = self.config()
        output = self.root / 'new.yaml'
        vm.write_new(str(output), config)
        self.assertEqual(json.loads(output.read_text()), config)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError): vm.write_new(str(output), {})
        self.assertEqual(json.loads(output.read_text()), config)
        symlink = self.root / 'link.yaml'; symlink.symlink_to(output)
        with self.assertRaises(FileExistsError): vm.write_new(str(symlink), {})

    def test_check_only_never_creates_output_or_starts_process(self):
        output = self.root / 'ignored.yaml'
        stdout = io.StringIO()
        with patch('subprocess.run', side_effect=AssertionError('Must not invoke tools')), contextlib.redirect_stdout(stdout):
            code = vm.main(['--bridge-socket', str(self.socket_path), '--source', str(ROOT), '--output', str(output), '--check-only'])
        self.assertEqual(code, 0)
        self.assertFalse(output.exists())
        report = json.loads(stdout.getvalue())
        self.assertFalse(report['vm_started'])
        self.assertFalse(report['bridge_mode_verified'])
        self.assertFalse(report['nested_macvlan_verified'])


if __name__ == '__main__': unittest.main()
