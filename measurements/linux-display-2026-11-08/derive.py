#!/usr/bin/env python3
"""Independently verify this captured series and regenerate derived.csv/audit.json."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import statistics
import struct

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NAMES = ('egui', 'gtk', 'slint', 'qt', 'tauri')
FIELDS = ('Rss', 'Pss', 'Private_Clean', 'Private_Dirty', 'Shared_Clean', 'Shared_Dirty', 'Anonymous', 'Swap')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

sources = {}
for line in (ROOT/'build/source-hashes.txt').read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    assert sha(REPO/name) == digest, name
    sources[name] = digest
for name in ('egui', 'slint', 'tauri'):
    assert (ROOT/f'build/{name}-Cargo.lock').read_bytes() == (REPO/f'examples/{name}/Cargo.lock').read_bytes()
assert (ROOT/'build/source-resolution.patch').read_bytes() == b''
assert read(ROOT/'measurement-receipt.json')['exit_code'] == 0
records, images, binary_hashes = [], {}, {}
smaps_checked = 0
for phase in ('preflight', 'results'):
    matrix = read(ROOT/phase/'matrix-outcome.json')
    assert matrix['status'] == 'passed' and len(matrix['completed_cases']) == 10
    for name in NAMES:
        for backend in ('x11', 'wayland'):
            case = f'{name}-{backend}'
            folder = ROOT/phase/case
            outcome = read(folder/'outcome.json')
            rows = read(folder/'samples.json')
            assert outcome['status'] == 'passed' and outcome['cleanup_status'] == 'clean'
            assert outcome['cleanup_survivors'] == []
            diagnostic = outcome['diagnostic']
            assert diagnostic == dict(name=name, backend=backend, content_width=960, content_height=640, ready=True)
            assert outcome['probe_uid'] == 0 and outcome['expected_app_uid'] == 1001
            assert all(p['uid'] == 1001 for p in outcome['desktop_processes'])
            identities = [{(p['pid'], p['created']) for p in row['processes']} for row in rows]
            # These captures have fixed families throughout; no born/vanished helper estimator is needed.
            assert all(ids == identities[0] for ids in identities)
            assert len(identities[0]) == (3 if name == 'tauri' else 1)
            assert all(p['uid'] == 1001 for row in rows for p in row['processes'])
            for point in ('start', 'end'):
                path = folder/f'{point}.png'
                assert struct.unpack('>II', path.read_bytes()[16:24]) == (1280, 720)
                assert sha(path) == outcome['screenshots'][point]['sha256']
                images[str(path.relative_to(ROOT))] = sha(path)
            if phase == 'results':
                assert sha(folder/'start.png') == sha(folder/'end.png')
            if name in binary_hashes:
                assert binary_hashes[name] == outcome['binary_sha256']
            binary_hashes[name] = outcome['binary_sha256']
            for path in folder.glob('*.smaps.gz'):
                grouped, active = {}, None
                for line in gzip.decompress(path.read_bytes()).decode().splitlines():
                    if re.match(r'^[0-9a-f]+-[0-9a-f]+ ', line):
                        parts = line.split(maxsplit=5)
                        active = grouped.setdefault(parts[5] if len(parts) == 6 else '[anonymous]', dict.fromkeys(FIELDS, 0))
                    elif active is not None and ':' in line:
                        key, value = line.split(':', 1)
                        if key in FIELDS:
                            active[key] += int(value.split()[0])
                assert grouped == read(path.with_suffix('').with_suffix('.json'))['mappings_kib']
                smaps_checked += 1
            if phase == 'preflight':
                assert len(rows) == 2
                continue
            assert len(rows) == 121
            elapsed = rows[-1]['monotonic'] - rows[0]['monotonic']
            cpu = sum(p['cpu_seconds'] for p in rows[-1]['processes']) - sum(p['cpu_seconds'] for p in rows[0]['processes'])
            rss = statistics.median(sum(p['rollup_kib']['Rss'] for p in row['processes'])/1024 for row in rows[1:])
            pss = statistics.median(sum(p['rollup_kib']['Pss'] for p in row['processes'])/1024 for row in rows[1:])
            stat_rss = statistics.median(sum(p['stat_rss_bytes'] for p in row['processes'])/2**20 for row in rows[1:])
            recorded = outcome['summary']
            for actual, expected in ((rss, recorded['family_rss_mib']['median']), (pss, recorded['family_pss_mib']['median']),
                                     (stat_rss, recorded['family_stat_rss_mib']['median']), (cpu*100/elapsed, recorded['observed_cpu_percent_one_core'])):
                assert abs(actual-expected) < 1e-9, (case, actual, expected)
            records.append(dict(framework=name, backend=backend, rss_mib=rss, pss_mib=pss, stat_rss_mib=stat_rss,
                                cpu_percent_one_core=cpu*100/elapsed, cpu_seconds=cpu, elapsed_seconds=elapsed,
                                sample_intervals=120, processes=len(identities[0]), binary_sha256=outcome['binary_sha256']))
with (ROOT/'derived.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(records)
(ROOT/'audit.json').write_text(json.dumps(dict(status='passed', source_files_verified=len(sources),
    preflight_cases=10, measured_cases=10, smaps_snapshots_verified=smaps_checked,
    stable_process_families=True, app_and_desktop_uid=1001, probe_uid=0,
    binary_hashes=binary_hashes, screenshot_hashes=images), indent=2)+'\n')
print(f'PASS: {len(sources)} source files, 20 cases, {smaps_checked} smaps snapshots, 40 PNGs; regenerated derived.csv/audit.json')
