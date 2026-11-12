"""One-time reproduction of the reviewed 2026-11-12 evidence import.

This script is removed with its temporary workflow after publication. It never
runs the archived applications and never changes the measured source commits.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

REPO = 'HeyVasily/rust-desktop-comparison'
BRANCH = 'codex/desktop-integration-baseline'
ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / 'measurements/desktop-integrated-2026-11-12'
EXPECTED = {
    13963776786: 'e3c97a91721d46d61aaa21e1f0d4e1ee4f39c601d5e7e4dd1567f9d83a64e8fc',
    13963700719: 'b51810d262aed0600dd10980874120b4e46eb92b589025481c617ad0840fdd6e',
    13963437647: '8ffe80c689f609fb007161453661634ed9cd6d759a1bab699371738289a2c9f3',
    13962897927: '201c411fb5afc661e19990f1028efca4f085945c1d066f7abdf5bbfc20bf784e',
    13962483476: 'deb4b9f0de3b70f56ccb05b1483d4c16b8186be8c019038f25ac7ac9d3d05734',
    13962256627: '2f5834183d99adf743fb27711e61b5316c53ba309f0d1d3414525fe97371a8a0',
    13962204059: '47b4e20a10da8b59ebf124cff92634c4f3795b6cfc3dd7a70cdfef2e45b437db',
    13961767557: 'b60bff4816a381f58a78dd0d18fee25cce100abc5616cc173644f9689292179c',
    13968705719: '092ec9c7490d5397076ac0c3d20f975087acfafe223efcc8c66fabfc519eeaa4',
    13966103624: 'c86b5211e50009cabe4b2ca31009bbf669718c3db77332590df057cf27d257f7',
    13965723963: '79957c002551d27e3279f569a8ca8003ae59396b96c650f1d855ad8ebf17cfd0',
}


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF_NAME') != BRANCH:
        raise RuntimeError('This import is restricted to the reviewed repository and branch')
    archives = json.loads((SERIES / 'archives.json').read_text())
    if len(archives) != 11 or {a['id'] for a in archives} != set(EXPECTED):
        raise ValueError('Unexpected artifact inventory')
    if sum(a['selection'] == 'current' for a in archives) != 9:
        raise ValueError('Exactly nine current archives are required')
    with tempfile.TemporaryDirectory(prefix='verified-desktop-evidence-') as tmp:
        base = Path(tmp)
        selected = base / 'selected'
        selected.mkdir()
        for a in archives:
            expected = EXPECTED[a['id']]
            if a['digest'] != 'sha256:' + expected:
                raise ValueError('Artifact digest differs from the reviewed manifest')
            name = a['name']
            if Path(name).name != name or '/' in name or '\\' in name or name in ('.', '..'):
                raise ValueError('Unsafe artifact name')
            archive_path = base / (name + '.zip')
            with archive_path.open('wb') as out:
                subprocess.run(['gh', 'api', f'/repos/{REPO}/actions/artifacts/{a["id"]}/zip'], stdout=out, check=True)
            if hashlib.sha256(archive_path.read_bytes()).hexdigest() != expected:
                raise ValueError('Downloaded archive checksum mismatch: ' + name)
            target = selected / name if a['selection'] == 'current' else base / name
            target.mkdir()
            with zipfile.ZipFile(archive_path) as archive:
                for item in archive.infolist():
                    path = PurePosixPath(item.filename)
                    if path.is_absolute() or '..' in path.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                        raise ValueError('Unsafe ZIP member: ' + item.filename)
                archive.extractall(target)
            print('Verified and extracted ' + name, flush=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/import_native_run.py'),
                        '43251948886,43263287428', str(selected), SERIES.name], check=True, cwd=ROOT)
        sys.path.insert(0, str(ROOT / 'tools'))
        from import_native_run import copy_evidence
        for rep in (1, 2):
            source = base / f'native-macos-15-43251948886-r{rep}'
            target = ROOT / 'measurements/native-43251948886' / f'r{rep}' / 'macos-15'
            copy_evidence(source, target, rep, 'macos-15', ROOT / 'screenshots/native-43251948886/macos-15')
        subprocess.run([sys.executable, str(ROOT / 'tools/build_desktop_site_data.py'), str(SERIES)], check=True, cwd=ROOT)
    paths = []
    for name in ('measurements/native-43251948886', 'measurements/native-43263287428'):
        paths.extend(p for p in (ROOT / name).rglob('*') if p.is_file())
    paths.extend(SERIES / name for name in ('archives.json', 'workflow-runs.json'))
    (SERIES / 'EVIDENCE-SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in sorted(paths)))
    print(f'Retained {len(paths)} evidence files with SHA-256 checksums.')


if __name__ == '__main__':
    main()
