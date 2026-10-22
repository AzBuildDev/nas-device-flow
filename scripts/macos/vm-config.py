#!/usr/bin/env python3
"""Prepare an experimental Lima gateway VM configuration without starting it."""
import argparse
import json
import os
import platform
import stat
import sys
from pathlib import Path

VERSION = '0.3.0-rc.1'
ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURES = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'x86_64': 'x86_64', 'amd64': 'x86_64'}


def safe_path(value, label):
    if not isinstance(value, str) or not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(label + ' must not be empty or contain control characters')
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(label + ' must be an absolute path')
    # Lima expands Go templates in paths; do not let user text become a template.
    if '{{' in value or '}}' in value:
        raise ValueError(label + ' must not contain template expressions')
    return path


def make_config(bridge_socket, source, architecture=None):
    socket_path = safe_path(bridge_socket, 'Bridge socket')
    try:
        socket_stat = socket_path.stat()
    except OSError as error:
        raise ValueError('Bridge socket must already exist') from error
    if not stat.S_ISSOCK(socket_stat.st_mode):
        raise ValueError('Bridge socket must be a Unix socket, not a file or directory')
    source_path = safe_path(source, 'Source directory').resolve()
    safe_path(str(source_path), 'Resolved source directory')
    if not source_path.is_dir() or not (source_path / 'compose.yaml').is_file() or not (source_path / 'app' / 'server.py').is_file():
        raise ValueError('Source directory must be the NAS Device Flow repository')
    requested = architecture or platform.machine()
    if requested not in ARCHITECTURES:
        raise ValueError('Architecture must be aarch64 or x86_64 (arm64 and amd64 aliases are accepted)')
    return {
        'minimumLimaVersion': '2.0.0',
        'base': 'template:_images/ubuntu-lts',
        'vmType': 'vz',
        'arch': ARCHITECTURES[requested],
        'cpus': 2,
        'memory': '2GiB',
        'disk': '20GiB',
        'mountType': 'virtiofs',
        'mounts': [{'location': str(source_path), 'mountPoint': '/mnt/ndf-source', 'writable': False}],
        'networks': [{'socket': str(socket_path), 'interface': 'ndflan', 'metric': 50}],
        'containerd': {'system': False, 'user': False},
    }


def write_new(output, config):
    path = safe_path(output, 'Output file')
    if not path.parent.is_dir():
        raise ValueError('Output parent directory must already exist')
    # O_EXCL rejects existing files, directories and symlinks without following them.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge-socket', required=True, help='Existing absolute socket_vmnet Unix socket; externally managed')
    parser.add_argument('--source', default=str(ROOT), help='Absolute repository root mounted read-only in guest')
    parser.add_argument('--arch', choices=sorted(ARCHITECTURES), help='Guest architecture; defaults to host')
    parser.add_argument('--output', help='New absolute output file path (JSON is valid YAML); never overwritten')
    parser.add_argument('--check-only', action='store_true', help='Print validated configuration as JSON; do not write a file')
    args = parser.parse_args(argv)
    if not args.check_only and not args.output:
        parser.error('--output is required unless --check-only is used')
    try:
        config = make_config(args.bridge_socket, args.source, args.arch)
        if args.check_only:
            print(json.dumps({'version': VERSION, 'experimental': True, 'config': config,
                              'bridge_mode_verified': False, 'nested_macvlan_verified': False,
                              'vm_started': False, 'docker_installed_by_generator': False}, ensure_ascii=False, indent=2))
        else:
            output = write_new(args.output, config)
            print(json.dumps({'version': VERSION, 'experimental': True, 'output': str(output),
                              'bridge_mode_verified': False, 'nested_macvlan_verified': False,
                              'vm_started': False, 'docker_installed_by_generator': False}, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({'error': str(error), 'vm_started': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
