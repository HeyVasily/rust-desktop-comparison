#!/usr/bin/env python3
"""Ten paired Linux display cases; privileged reader, ordinary-user GUI processes."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import statistics
import subprocess
import sys
import tempfile
import time

import psutil
from PIL import Image, ImageGrab, ImageStat

from gtk_memory_probe import FIELDS, parse_smaps, write_json
from native_probe import Family, find_window, scope_snapshot, summarize

NAMES = ('egui', 'gtk', 'slint', 'qt', 'tauri')
TITLES = dict(egui='Veranda egui comparison', gtk='Veranda GTK comparison',
              slint='Veranda Slint comparison', qt='Veranda Qt Widgets comparison',
              tauri='Veranda Tauri comparison')
BINARIES = dict(egui='release/veranda-egui-comparison', gtk='gtk-control',
                slint='release/veranda-slint-comparison', qt='qt/veranda-qt-comparison',
                tauri='release/veranda-tauri-comparison')


def display_environment(base, backend):
    env = base.copy()
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'WAYLAND_SOCKET', 'GSK_RENDERER', 'GDK_DISABLE',
                'WLR_XWAYLAND', 'WINIT_UNIX_BACKEND', 'GTK_THEME', 'GTK_A11Y', 'NO_AT_BRIDGE',
                'QT_SCALE_FACTOR', 'QT_SCREEN_SCALE_FACTORS', 'DBUS_SESSION_BUS_ADDRESS'):
        env.pop(key, None)
    env.update(GDK_BACKEND=backend, QT_QPA_PLATFORM='xcb' if backend == 'x11' else 'wayland',
               XDG_SESSION_TYPE=backend, LIBGL_ALWAYS_SOFTWARE='1', LANG='C.UTF-8',
               GDK_SCALE='1', GDK_DPI_SCALE='1', COMPARISON_DISPLAY_DIAGNOSTICS='1')
    return env


def read_diagnostic(path, name, backend):
    for line in path.read_text().splitlines():
        if not line.startswith('DISPLAY_DIAGNOSTIC '):
            continue
        info = json.loads(line.removeprefix('DISPLAY_DIAGNOSTIC '))
        if info.get('name') != name or info.get('backend') != backend:
            raise RuntimeError(f'Actual backend/name mismatch: {info}')
        if not info.get('ready') or [info.get('content_width'), info.get('content_height')] != [960, 640]:
            raise RuntimeError(f'Actual content is not ready at 960x640: {info}')
        return info
    return None


def sample(family):
    rows = []
    for process in family.refresh():
        values = {}
        for line in Path(f'/proc/{process.pid}/smaps_rollup').read_text().splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                if key in FIELDS:
                    values[key] = int(value.split()[0])
        cpu = process.cpu_times()
        rows.append(dict(pid=process.pid, created=process.create_time(), name=process.name(),
                         uid=process.uids().effective, cpu_seconds=cpu.user + cpu.system,
                         threads=process.num_threads(), rollup_kib=values,
                         rss_bytes=values['Rss'] * 1024, stat_rss_bytes=process.memory_info().rss))
    if not family.root.is_running() or family.root.status() == psutil.STATUS_ZOMBIE:
        raise RuntimeError('Application exited during measurement')
    if family.access_errors:
        raise RuntimeError(f'Incomplete process access: {sorted(family.access_errors)}')
    return dict(monotonic=time.monotonic(), wall_time=time.time(), processes=rows,
                family_rss_bytes=sum(p['rss_bytes'] for p in rows))


def summary(rows):
    result = summarize(rows)
    if result['late_discovered_preexisting_processes']:
        raise RuntimeError('Late helper discovery invalidates the CPU baseline')
    result['family_pss_mib'] = dict(median=statistics.median(
        sum(p['rollup_kib']['Pss'] for p in row['processes']) / 1024 for row in rows[1:]))
    result['family_stat_rss_mib'] = dict(median=statistics.median(
        sum(p['stat_rss_bytes'] for p in row['processes']) / 2**20 for row in rows[1:]))
    result['max_processes'] = max(len(row['processes']) for row in rows)
    result['max_threads'] = max(sum(p['threads'] for p in row['processes']) for row in rows)
    result['cpu_note'] = 'Percent of one logical core; zero means no recorded counter increment'
    return result


def mappings(family, output, phase):
    for process in family.refresh():
        raw = Path(f'/proc/{process.pid}/smaps').read_bytes()
        stem = output / f'{phase}-{process.pid}'
        stem.with_suffix('.smaps.gz').write_bytes(gzip.compress(raw, mtime=0))
        write_json(stem.with_suffix('.json'), dict(pid=process.pid, created=process.create_time(),
                   name=process.name(), mappings_kib=parse_smaps(raw.decode())))


def capture(path, backend, env, user):
    if backend == 'wayland':
        subprocess.run(['runuser', '-u', user, '--', 'grim', '-'], env=env,
                       stdout=path.open('wb'), check=True, timeout=10)
    else:
        ImageGrab.grab(xdisplay=env['DISPLAY']).save(path)
    with Image.open(path) as picture:
        if picture.size != (1280, 720):
            raise RuntimeError(f'Unexpected desktop dimensions: {picture.size}')
        # Exclude desktop edges/titlebars; one-shot native/DOM dimensions supplement
        # this heuristic. Final publication still requires visual artifact review.
        content = picture.convert('RGB').crop((320, 180, 960, 540))
        if max(ImageStat.Stat(content).stddev) < 2:
            raise RuntimeError('Central client capture is blank or uniform')
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), desktop_size=[1280, 720],
                inspection='Original desktop PNG; native content dimensions also required; inspect initial UI')


def run_case(args):
    name, backend = args.case.split('-')
    output = args.output / args.case
    output.mkdir(parents=True)
    output.chmod(0o755)
    account = pwd.getpwnam(args.user)
    if account.pw_uid == 0 or os.geteuid() != 0:
        raise RuntimeError('Run the reader as root and select an ordinary GUI user')
    executable = (args.target / BINARIES[name]).resolve()
    result = dict(name=name, backend=backend, status='failed', cleanup_status='unknown',
                  binary_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                  probe_uid=os.geteuid(), expected_app_uid=account.pw_uid,
                  limitations=['5Hz ancestry discovery can miss short-lived helpers and their final CPU interval',
                               'RSS counts shared pages per process; PSS apportions current sharing',
                               'Native Wayland verified by display handle; no claim that labwc disables its optional Xwayland support'])
    children, streams, family = [], [], None
    env = display_environment(os.environ, backend)
    def launch(command, label):
        stream = (output / f'{label}.log').open('w')
        streams.append(stream)
        child = subprocess.Popen(['runuser', '-u', args.user, '--', *command], env=env,
                                 stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        children.append(child)
        return child
    def wait_for(check, seconds=45):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Owned desktop/application process exited before readiness')
            if family is not None:
                family.refresh()
            value = check()
            if value:
                return value
            time.sleep(.1)
        raise RuntimeError('Readiness timed out')
    def poll_for(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            family.refresh()
            if family.access_errors:
                raise RuntimeError('Process ancestry access denied')
            time.sleep(min(.2, max(0, deadline-time.monotonic())))
    try:
        with tempfile.TemporaryDirectory(prefix='display-probe-', dir='/tmp') as runtime:
            os.chown(runtime, account.pw_uid, account.pw_gid)
            os.chmod(runtime, 0o700)
            env['XDG_RUNTIME_DIR'] = runtime
            launch(['dbus-daemon', '--session', '--nofork', '--print-address=1'], 'session-bus')
            env['DBUS_SESSION_BUS_ADDRESS'] = wait_for(lambda: next(
                (s for s in (output/'session-bus.log').read_text().splitlines() if s.startswith('unix:')), None))
            if backend == 'x11':
                env['DISPLAY'] = ':91'
                launch(['Xvfb', ':91', '-screen', '0', '1280x720x24', '-nolisten', 'tcp', '-ac'], 'display')
                wait_for(lambda: Path('/tmp/.X11-unix/X91').exists())
                launch(['openbox'], 'compositor')
                time.sleep(1)
            else:
                env.update(WLR_BACKENDS='headless', WLR_RENDERER='pixman', WLR_HEADLESS_OUTPUTS='1')
                launch(['labwc'], 'compositor')
                sockets = wait_for(lambda: [p for p in Path(runtime).glob('wayland-*') if p.is_socket()])
                env['WAYLAND_DISPLAY'] = sockets[0].name
            from native_probe import web_helpers
            before_helpers = web_helpers()
            pidfile = str(Path(runtime)/'application.pid')
            launch(['sh', '-c', 'echo $$ > "$1"; shift; exec "$@"', 'app-launch', pidfile, str(executable)], 'application')
            pid = wait_for(lambda: int(Path(pidfile).read_text()) if Path(pidfile).exists() and Path(pidfile).read_text().strip() else None)
            family = Family(pid)
            info = wait_for(lambda: read_diagnostic(output/'application.log', name, backend))
            if family.root.uids().effective != account.pw_uid or Path(family.root.exe()).resolve() != executable:
                raise RuntimeError('App PID/UID/executable binding failed')
            result['diagnostic'] = info
            result['environment'] = {k: env.get(k) for k in ('GDK_BACKEND','QT_QPA_PLATFORM','LIBGL_ALWAYS_SOFTWARE',
                  'GSK_RENDERER','GDK_DISABLE','WLR_BACKENDS','WLR_RENDERER','WLR_XWAYLAND','GDK_SCALE','GDK_DPI_SCALE')}
            result['desktop_processes'] = [dict(pid=p.pid, name=p.name(), uid=p.uids().effective)
                  for child in children[:-1] for p in psutil.Process(child.pid).children(recursive=True)]
            poll_for(args.settle)
            if backend == 'x11':
                result['window'] = find_window({p.pid for p in family.refresh()}, TITLES[name])
                if not result['window']:
                    raise RuntimeError('No visible X11 window matching app PID/title')
            unassigned, _ = scope_snapshot(family, before_helpers)
            if unassigned:
                raise RuntimeError(f'Unattributed WebKit helpers: {list(unassigned)}')
            result['screenshots'] = dict(start=capture(output/'start.png', backend, env, args.user))
            mappings(family, output, 'start')
            rows = [sample(family)]
            for _ in range(args.intervals):
                poll_for(1)
                rows.append(sample(family))
            write_json(output/'samples.json', rows)
            result['summary'] = summary(rows)
            result['screenshots']['end'] = capture(output/'end.png', backend, env, args.user)
            mappings(family, output, 'end')
            unassigned, _ = scope_snapshot(family, before_helpers)
            if unassigned or family.access_errors:
                raise RuntimeError('Final app-family attribution incomplete')
            if any(p['uid'] != account.pw_uid for row in rows for p in row['processes']):
                raise RuntimeError('Application family contains an unexpected effective UID')
            result['observed_processes'] = list(family.observed.values())
            result['xwayland_processes'] = [p.pid for p in psutil.process_iter(['name'])
                                            if (p.info['name'] or '').lower() == 'xwayland']
            result['status'] = 'passed'
    except Exception as error:
        result['reason'] = f'{type(error).__name__}: {error}'
    finally:
        survivors = family.cleanup() if family else []
        owned = []
        for child in children:
            try:
                owned.extend(psutil.Process(child.pid).children(recursive=True))
            except psutil.NoSuchProcess:
                pass
        for child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
        for p in owned:
            try:
                if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    p.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(owned, timeout=5)
        survivors += [p.pid for p in alive if p.status() != psutil.STATUS_ZOMBIE]
        for stream in streams:
            stream.close()
        result['cleanup_survivors'] = survivors
        result['cleanup_status'] = 'clean' if not survivors else 'failed'
        if survivors:
            result['status'] = 'failed'
        write_json(output/'outcome.json', result)
        for artifact in output.rglob('*'):
            artifact.chmod(0o755 if artifact.is_dir() else 0o644)
        print(json.dumps(dict(case=args.case,status=result['status'],cleanup=result['cleanup_status'],
                              summary=result.get('summary'),reason=result.get('reason'))), flush=True)
    return 0 if result['status'] == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--settle', type=int, default=30)
    parser.add_argument('--intervals', type=int, default=120)
    parser.add_argument('--framework', choices=('all', *NAMES), default='all')
    parser.add_argument('--backend', choices=('both', 'x11', 'wayland'), default='both')
    parser.add_argument('--case', choices=[f'{n}-{b}' for n in NAMES for b in ('x11','wayland')])
    args = parser.parse_args()
    args.target,args.output = args.target.resolve(),args.output.resolve()
    if args.settle < 0 or args.intervals < 1:
        parser.error('Invalid sample duration')
    if args.case:
        return run_case(args)
    args.output.mkdir(parents=True,exist_ok=True)
    args.output.chmod(0o755)
    outcomes = {}
    for name in (NAMES if args.framework == 'all' else (args.framework,)):
        for backend in (('x11','wayland') if args.backend == 'both' else (args.backend,)):
            case = f'{name}-{backend}'
            command = [sys.executable,__file__,'--target',str(args.target),'--output',str(args.output),
                       '--user',args.user,'--case',case,'--settle',str(args.settle),'--intervals',str(args.intervals)]
            print(f'BEGIN {case}',flush=True)
            subprocess.run(command,check=True,timeout=args.settle+args.intervals+180)
            outcomes[case] = json.loads((args.output/case/'outcome.json').read_text())
        if args.backend == 'both' and outcomes[f'{name}-x11']['binary_sha256'] != outcomes[f'{name}-wayland']['binary_sha256']:
            raise RuntimeError(f'{name}: binary changed between paired cases')
    write_json(args.output/'summary.json',outcomes)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
