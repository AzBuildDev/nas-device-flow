"""Safety contracts for the Windows deployment packaging (not LAN validation)."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('windows_package', ROOT/'deploy/windows/build-package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class WindowsGatewayTests(unittest.TestCase):
    def test_package_blocks_private_and_traversal_paths(self):
        for name in ('runtime/config.yaml', '.env', 'private/state.json', '.windows-state/network.json',
                     '../secret', '/absolute', 'x/config.local.json', 'x/password.key'):
            self.assertFalse(package.allowed(name), name)
        for name in ('app/server.py', 'examples/settings.json', '.env.example', 'deploy/windows/VERSION'):
            self.assertTrue(package.allowed(name), name)

    def test_guest_reuses_backend_and_blocks_dhcp_startup(self):
        script = (ROOT/'deploy/windows/guest-install.sh').read_text(encoding='utf-8')
        self.assertIn('sh scripts/install.sh --prepare-only', script)
        self.assertIn('NDF_VERIFIED_BRIDGED_LAB', script)
        self.assertLess(script.index('[ ! -e runtime/control-center/dhcp.enabled ]'), script.index('docker compose up'))
        self.assertLess(script.index('mihomo -t'), script.index('docker compose up'))
        self.assertNotIn('dhcp.py enable', script)

    def test_import_does_not_change_host_network_or_start_vm(self):
        script = (ROOT/'deploy/windows/Import-GatewayVM.ps1').read_text(encoding='utf-8')
        for command in ('New-VMSwitch', 'Enable-WindowsOptionalFeature', 'Start-VM ', 'Set-NetIPInterface', 'Set-DnsClientServerAddress'):
            self.assertNotIn(command, script)
        self.assertIn('SupportsShouldProcess=$true', script)
        self.assertIn('Get-FileHash', script)
        self.assertIn("$switch.SwitchType -ne 'External'", script)


if __name__ == '__main__':
    unittest.main()
