#!/usr/bin/env python3
"""Linux GTK renderer/backend A/B. Run as an ordinary user in a disposable desktop VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import time

import psutil
from PIL import Image, ImageGrab, ImageStat

FIELDS = ('Rss', 'Pss', 'Private_Clean', 'Private_Dirty', 'Shared_Clean', 'Shared_Dirty', 'Anonymous', 'Swap')
HEADER = re.compile(r'^[0-9a-f]+-[0-9a-f]+\s')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def parse_smaps(text):
    """Keep kernel kB units (KiB); group all mappings of one file, plus anonymous regions."""
    groups = {}
    current = None
    for line in text.splitlines():
        if HEADER.match(line):
            parts = line.split(None, 5)
            name = parts[5] if len(parts) == 6 else '[anonymous]'
            current = groups.setdefault(name, dict.fromkeys(FIELDS, 0))
        elif current is not None and ':' in line:
            key, value = line.split(':', 1)
            if key in FIELDS:
                current[key] += int(value.split()[0])
    if not groups:
        raise ValueError('No smaps mappings')
    return dict(sorted(groups.items(), key=lambda item: (-item[1]['Rss'], item[0])))


def snapshot(process, destination):
    raw = Path(f'/proc/{process.pid}/smaps').read_text()
    destination.with_suffix('.smaps').write_text(raw)
    groups = parse_smaps(raw)
    write_json(destination.with_suffix('.json'), groups)
    return groups


def sample(process):
    if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
        raise RuntimeError('Application exited during sampling')
    family = [process] + process.children(recursive=True)
    rows = []
    for member in family:
        rollup = {}
        for line in Path(f'/proc/{member.pid}/smaps_rollup').read_text().splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                if key in FIELDS:
                    rollup[key] = int(value.split()[0])
        cpu = member.cpu_times()
        rows.append(dict(pid=member.pid, created=member.create_time(), name=member.name(),
                         cpu_seconds=cpu.user + cpu.system, threads=member.num_threads(),
                         stat_rss_bytes=member.memory_info().rss, rollup_kib=rollup))
    return dict(monotonic=time.monotonic(), processes=rows)


def summarize(samples):
    elapsed = samples[-1]['monotonic'] - samples[0]['monotonic']
    # Charge only increments between observations of the same process identity.
    cpu = 0
    for before, after in zip(samples, samples[1:]):
        old = {(p['pid'], p['created']): p['cpu_seconds'] for p in before['processes']}
        for p in after['processes']:
            key = p['pid'], p['created']
            if key in old:
                cpu += max(0, p['cpu_seconds'] - old[key])
    return dict(intervals=len(samples)-1, elapsed_seconds=elapsed, cpu_seconds=cpu,
                cpu_percent_one_core=100 * cpu / elapsed,
                cpu_resolution_note='0 means no recorded CPU-counter increment',
                rss_mib=statistics.median(sum(p['rollup_kib']['Rss'] for p in s['processes']) / 1024 for s in samples),
                pss_mib=statistics.median(sum(p['rollup_kib']['Pss'] for p in s['processes']) / 1024 for s in samples),
                stat_rss_mib=statistics.median(sum(p['stat_rss_bytes'] for p in s['processes']) / 2**20 for s in samples),
                processes=sorted({p['name'] for s in samples for p in s['processes']}),
                max_family_processes=max(len(s['processes']) for s in samples),
                max_threads=max(sum(p['threads'] for p in s['processes']) for s in samples))


def wait_for(check, children, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if any(child.poll() is not None for child in children):
            raise RuntimeError('Desktop/application exited before readiness')
        value = check()
        if value:
            return value
        time.sleep(.1)
    raise RuntimeError('Desktop/application readiness timed out')


def diagnostic(path):
    for line in path.read_text().splitlines():
        if line.startswith('GTK_DIAGNOSTIC '):
            return json.loads(line.removeprefix('GTK_DIAGNOSTIC '))
    return None


def screenshot(path, backend, env):
    if backend == 'wayland':
        subprocess.run(['grim', str(path)], env=env, check=True, timeout=10)
    else:
        ImageGrab.grab(xdisplay=env['DISPLAY']).save(path)
    with Image.open(path) as picture:
        stddev = ImageStat.Stat(picture.convert('RGB')).stddev
        if max(stddev) < 5:
            raise RuntimeError('Blank desktop capture')
        return dict(size=list(picture.size), stddev=stddev,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def run_case(args):
    backend, renderer, *extra = args.case.split('-')
    output = args.output / args.case
    output.mkdir(parents=True)
    children, streams = [], []
    env = os.environ.copy()
    for key in ('GSK_RENDERER', 'GDK_DISABLE', 'DISPLAY', 'WAYLAND_DISPLAY', 'GTK_THEME', 'GTK_A11Y', 'NO_AT_BRIDGE'):
        env.pop(key, None)
    env.update(GDK_BACKEND=backend, XDG_SESSION_TYPE=backend, LIBGL_ALWAYS_SOFTWARE='1',
               COMPARISON_GTK_DIAGNOSTICS='1', LANG='C.UTF-8', GDK_SCALE='1', GDK_DPI_SCALE='1')
    if renderer != 'default':
        env['GSK_RENDERER'] = renderer
    if extra:
        env['GDK_DISABLE'] = 'gl,vulkan'
    def spawn(command, log):
        stream = (output / log).open('w')
        streams.append(stream)
        child = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        children.append(child)
        return child
    cleanup = []
    with tempfile.TemporaryDirectory(prefix='gtk-runtime-', dir='/tmp') as runtime:
        env['XDG_RUNTIME_DIR'] = runtime
        try:
            if backend == 'x11':
                env['DISPLAY'] = ':91'
                spawn(['Xvfb', ':91', '-screen', '0', '1280x900x24', '-nolisten', 'tcp'], 'display.log')
                wait_for(lambda: Path('/tmp/.X11-unix/X91').exists(), children)
                spawn(['openbox'], 'compositor.log')
                time.sleep(1)
            else:
                env.update(WLR_BACKENDS='headless', WLR_RENDERER='pixman', WLR_HEADLESS_OUTPUTS='1', WLR_XWAYLAND='0')
                spawn(['labwc'], 'compositor.log')
                sockets = wait_for(lambda: [p for p in Path(runtime).glob('wayland-*') if p.is_socket()], children)
                env['WAYLAND_DISPLAY'] = sockets[0].name
            app = spawn([str(args.binary)], 'application.log')
            info = wait_for(lambda: diagnostic(output / 'application.log'), children)
            expected = 'GdkX11Display' if backend == 'x11' else 'GdkWaylandDisplay'
            if info['display'] != expected or not info['mapped'] or info['renderer'] == 'unavailable':
                raise RuntimeError(f'Unexpected GTK diagnostic: {info}')
            if renderer == 'cairo' and info['renderer'] != 'GskCairoRenderer':
                raise RuntimeError('Cairo renderer request did not take effect')
            if [info['width'], info['height']] != [960, 640]:
                raise RuntimeError(f'Unexpected client dimensions: {info}')
            write_json(output / 'configuration.json', dict(diagnostic=info, requested_renderer=renderer,
                       environment={k: env.get(k) for k in ('GSK_RENDERER', 'GDK_DISABLE', 'GDK_BACKEND', 'LIBGL_ALWAYS_SOFTWARE',
                         'WLR_BACKENDS', 'WLR_RENDERER', 'WLR_XWAYLAND', 'GDK_SCALE', 'GDK_DPI_SCALE', 'GTK_A11Y', 'LANG')},
                       settle_seconds=args.settle, requested_intervals=args.intervals))
            time.sleep(args.settle)
            process = psutil.Process(app.pid)
            start_image = screenshot(output / 'start.png', backend, env)
            snapshot(process, output / 'start-mappings')
            samples = [sample(process)]
            for _ in range(args.intervals):
                time.sleep(1)
                samples.append(sample(process))
            write_json(output / 'samples.json', samples)
            summary = summarize(samples)
            summary['diagnostic'] = info
            summary['screenshots'] = dict(start=start_image, end=screenshot(output / 'end.png', backend, env))
            snapshot(process, output / 'end-mappings')
            write_json(output / 'threads.json', [dict(id=t.id, user_time=t.user_time, system_time=t.system_time) for t in process.threads()])
            write_json(output / 'summary.json', summary)
            print(json.dumps(dict(case=args.case, **summary)), flush=True)
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)
                cleanup.append(dict(pid=child.pid, exit_code=child.returncode))
            for stream in streams:
                stream.close()
            write_json(output / 'cleanup.json', cleanup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--settle', type=int, default=30)
    parser.add_argument('--intervals', type=int, default=120)
    parser.add_argument('--case', choices=['x11-default', 'x11-cairo', 'wayland-default', 'wayland-cairo', 'x11-cairo-no-gpu'])
    args = parser.parse_args()
    if args.intervals < 1 or args.settle < 0:
        parser.error('Positive intervals and nonnegative settle required')
    args.binary, args.output = args.binary.resolve(), args.output.resolve()
    if args.case:
        run_case(args)
        return
    args.output.mkdir(parents=True, exist_ok=True)
    cases = ['x11-default', 'x11-cairo', 'wayland-default', 'wayland-cairo']
    def run(case):
        subprocess.run(['dbus-run-session', '--', sys.executable, __file__, '--binary', str(args.binary),
                        '--output', str(args.output), '--settle', str(args.settle), '--intervals', str(args.intervals),
                        '--case', case], check=True)
    for case in cases:
        print(f'BEGIN {case}', flush=True)
        run(case)
    cairo_maps = json.loads((args.output / 'x11-cairo/end-mappings.json').read_text())
    llvm_kib = sum(v['Rss'] for name, v in cairo_maps.items() if 'libLLVM' in name)
    if llvm_kib > 1024:
        write_json(args.output / 'extra-control-reason.json', dict(llvm_resident_kib=llvm_kib,
                   hypothesis='Cairo still loads graphics driver code during X11 display initialization; disable GL and Vulkan to test its contribution.'))
        print('BEGIN x11-cairo-no-gpu (resident LLVM despite Cairo)', flush=True)
        run('x11-cairo-no-gpu')
        cases.append('x11-cairo-no-gpu')
    write_json(args.output / 'summary.json', {case: json.loads((args.output / case / 'summary.json').read_text()) for case in cases})


if __name__ == '__main__':
    main()
