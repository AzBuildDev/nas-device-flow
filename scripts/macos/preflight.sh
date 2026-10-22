#!/bin/sh
# Read-only macOS host inventory. Does not install software or change networking.
set -eu
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' '{"schema_version":1,"error":"python3_required","message":"Install Python 3, then rerun this read-only check."}'
    exit 2
fi
exec python3 - <<'PY'
import ipaddress
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(args, timeout=5):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        if result.returncode == 0:
            return result.stdout.strip(), None
        return None, 'command_failed'
    except subprocess.TimeoutExpired:
        return None, 'timeout'
    except (OSError, UnicodeError):
        return None, 'unavailable'


def value(args):
    return run(args)[0]


report = {
    'schema_version': 1,
    'read_only': True,
    'host': {'system': platform.system(), 'architecture': platform.machine()},
    'native_gateway_supported': False,
    'network': {'interfaces': [], 'default_ipv4_gateway': None, 'default_interface': None},
    'docker': {'installed': shutil.which('docker') is not None, 'daemon_reachable': False},
    'virtualization': {},
    'notes': [],
}
if platform.system() != 'Darwin':
    report['error'] = 'macos_required'
    report['notes'].append('This inventory script is intended for macOS.')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(2)

report['host']['macos_version'] = value(['/usr/bin/sw_vers', '-productVersion'])
report['host']['macos_build'] = value(['/usr/bin/sw_vers', '-buildVersion'])
report['host']['process_translated'] = value(['/usr/sbin/sysctl', '-in', 'sysctl.proc_translated']) == '1'

# ifconfig exposes only interface names, IPv4 addresses, masks and link status here.
# Hardware addresses, host names and wireless network names are intentionally omitted.
raw, error = run(['/sbin/ifconfig', '-a'])
if error:
    report['network']['inventory_error'] = error
else:
    current = None
    for line in raw.splitlines():
        match = re.match(r'^([^\s:]+):', line)
        if match:
            current = {'name': match.group(1), 'ipv4': [], 'status': None}
            report['network']['interfaces'].append(current)
        elif current is not None:
            match = re.search(r'\binet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+(\S+)', line)
            if match:
                address, mask = match.groups()
                try:
                    mask_number = int(mask, 16) if mask.startswith('0x') else int(ipaddress.IPv4Address(mask))
                    prefix = ipaddress.IPv4Network('0.0.0.0/' + str(ipaddress.IPv4Address(mask_number))).prefixlen
                    current['ipv4'].append({'address': address, 'prefix_length': prefix})
                except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                    pass
            match = re.search(r'\bstatus:\s+(\S+)', line)
            if match:
                current['status'] = match.group(1)
raw, error = run(['/sbin/route', '-n', 'get', '-inet', 'default'])
if raw:
    for key, field in [('gateway', 'default_ipv4_gateway'), ('interface', 'default_interface')]:
        match = re.search(r'^\s*' + key + r':\s+(\S+)', raw, re.MULTILINE)
        if match:
            report['network'][field] = match.group(1)
else:
    report['network']['default_route_error'] = error

if report['docker']['installed']:
    docker = shutil.which('docker')
    context, context_error = run([docker, 'context', 'show'])
    report['docker']['current_context'] = context
    if context_error:
        report['docker']['context_error'] = context_error
    # Restrict inspection to non-secret fields; do not print registry credentials,
    # context endpoints, environment values or full docker info output.
    template = '{{json .OSType}}|{{json .Architecture}}|{{json .OperatingSystem}}'
    raw, error = run([docker, 'info', '--format', template], timeout=8)
    if raw:
        try:
            operating_type, architecture, operating_system = [json.loads(part) for part in raw.split('|', 2)]
            report['docker'].update(daemon_reachable=True, daemon_os=operating_type,
                                    daemon_architecture=architecture, operating_system=operating_system,
                                    docker_desktop='docker desktop' in (operating_system or '').lower())
        except (ValueError, TypeError):
            report['docker']['info_error'] = 'unexpected_format'
    else:
        report['docker']['info_error'] = error

report['virtualization']['hypervisor_available'] = value(['/usr/sbin/sysctl', '-n', 'kern.hv_support']) == '1'
report['virtualization']['tools'] = {name: shutil.which(name) is not None for name in [
    'limactl', 'colima', 'vfkit', 'qemu-system-aarch64', 'qemu-system-x86_64',
    'tart', 'multipass', 'prlctl', 'VBoxManage', 'virsh',
]}
report['virtualization']['applications'] = {name: Path('/Applications', name + '.app').exists() for name in [
    'Docker', 'UTM', 'Parallels Desktop', 'VMware Fusion', 'VirtualBox',
]}
report['notes'].append('Inventory only: the current Linux macvlan/DHCP gateway deployment is not a native macOS host mode.')
if report['docker'].get('docker_desktop'):
    report['notes'].append('Docker Desktop runs a Linux VM. A reachable daemon does not establish LAN macvlan or DHCP compatibility.')
report['notes'].append('No network, DNS, DHCP, routing, firewall, VPN or Docker settings were changed.')
print(json.dumps(report, ensure_ascii=False, indent=2))
PY
