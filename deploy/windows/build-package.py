#!/usr/bin/env python3
"""Reproducible tracked-source archive; never walks private runtime directories."""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_PARTS = {'runtime', 'private', '.windows-state', '.git', '.venv', '__pycache__'}


def allowed(name):
    path = PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts
            and not PRIVATE_PARTS.intersection(path.parts)
            and path.name not in {'.env', 'config.local.json'}
            and not path.name.endswith(('.local.json', '.log', '.key', '.pem')))


def build(output):
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(filter(None, names)):
            if not allowed(name):
                raise ValueError('Private/unsafe tracked path blocked: ' + name)
            path = ROOT / name
            if path.is_symlink():
                raise ValueError('Symlink blocked: ' + name)
            info = zipfile.ZipInfo('nas-device-flow/' + name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            # Git canonical LF content: Windows autocrlf does not change package bytes.
            content = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
            archive.writestr(info, content, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n', encoding='ascii')
    print(output.name + ' SHA256 ' + digest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist'/'nas-device-flow-windows-preview.zip')
    args = parser.parse_args()
    build(args.output)
