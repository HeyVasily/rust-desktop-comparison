#!/usr/bin/env python3
"""Bounded visible-window diagnostic on Windows/macOS/Linux X11; no GUI availability assumption."""
import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import statistics
import subprocess
import sys
import time

import psutil
from PIL import Image, ImageGrab, ImageStat


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def environment():
    result = dict(os=platform.platform(), architecture=platform.machine(),
                  processor=platform.processor(), logical_cpus=psutil.cpu_count(),
                  memory_bytes=psutil.virtual_memory().total, python=sys.version,
                  runner_image=os.getenv("ImageOS"), image_version=os.getenv("ImageVersion"),
                  commit=os.getenv("GITHUB_SHA"), run_id=os.getenv("GITHUB_RUN_ID"),
                  renderer="See each application.log; unknown unless reported by the app")
    if sys.platform == "darwin":
        result["cpu_model"] = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        with open("/System/Library/Frameworks/WebKit.framework/Resources/Info.plist", "rb") as stream:
            result["system_webkit_version"] = plistlib.load(stream).get("CFBundleVersion")
    return result


class Family:
    """Retain observed descendants after reparenting, keyed by PID and creation time."""
    def __init__(self, pid, external_scope=None):
        root = psutil.Process(pid)
        self.root = root
        self.known = {pid: root}
        self.observed = {}
        self.access_errors = set()
        self.external_scope = external_scope
        self.next_scope_refresh = 0.0

    def refresh(self):
        if self.external_scope and time.monotonic() >= self.next_scope_refresh:
            for process in self.external_scope.refresh():
                self.known[process.pid] = process
            self.next_scope_refresh = time.monotonic() + 1
        for process in list(self.known.values()):
            try:
                if process.is_running():
                    for child in process.children(recursive=True):
                        self.known[child.pid] = child
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                self.access_errors.add(process.pid)
        live = []
        for process in self.known.values():
            try:
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    identity = f"{process.pid}:{process.create_time()}"
                    self.observed[identity] = dict(pid=process.pid, name=process.name(),
                                                   created=process.create_time())
                    live.append(process)
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                self.access_errors.add(process.pid)
        return live

    def sample(self):
        rows = []
        for process in self.refresh():
            try:
                with process.oneshot():
                    cpu = process.cpu_times()
                    rows.append(dict(pid=process.pid, created=process.create_time(),
                                     name=process.name(), rss_bytes=process.memory_info().rss,
                                     cpu_seconds=cpu.user + cpu.system))
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                self.access_errors.add(process.pid)
        if not self.root.is_running() or self.root.status() == psutil.STATUS_ZOMBIE:
            raise RuntimeError("Application exited during sampling")
        return dict(monotonic=time.monotonic(), wall_time=time.time(), processes=rows,
                    family_rss_bytes=sum(row["rss_bytes"] for row in rows))

    def cleanup(self):
        processes = self.refresh()
        for process in reversed(processes):
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                self.access_errors.add(process.pid)
        _, alive = psutil.wait_procs(processes, timeout=3)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                self.access_errors.add(process.pid)
        _, alive = psutil.wait_procs(alive, timeout=3)
        return [process.pid for process in alive]


def web_helpers():
    # WKWebView XPC services may be launched by launchd, outside the app's ancestry.
    found = {}
    for process in psutil.process_iter(["pid", "name", "create_time"]):
        name = process.info["name"] or ""
        if "webkit" in name.lower() or "msedgewebview2" in name.lower():
            found[f"{process.pid}:{process.info['create_time']}"] = process.info
    return found


def find_window(pids, title):
    if sys.platform == "win32":
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        matches = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def visit(handle, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            if pid.value not in pids or not user32.IsWindowVisible(handle) or user32.IsIconic(handle):
                return True
            text = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(handle) + 1)
            user32.GetWindowTextW(handle, text, len(text))
            if text.value != title:
                return True
            rect, origin = wintypes.RECT(), wintypes.POINT()
            if not user32.GetClientRect(handle, ctypes.byref(rect)):
                return True
            if not user32.ClientToScreen(handle, ctypes.byref(origin)):
                return True
            if rect.right > 0 and rect.bottom > 0:
                matches.append(dict(id=int(handle), pid=pid.value, title=text.value,
                                    rectangle=[origin.x, origin.y, origin.x + rect.right,
                                               origin.y + rect.bottom], bounds_kind="client"))
            return True

        user32.EnumWindows(visit, 0)
        return matches[0] if matches else None
    if sys.platform == "darwin":
        import Quartz
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID)
        for window in windows or []:
            if window.get("kCGWindowOwnerPID") not in pids or window.get("kCGWindowName") != title:
                continue
            bounds = window["kCGWindowBounds"]
            if bounds["Width"] > 0 and bounds["Height"] > 0 and window.get("kCGWindowLayer") == 0:
                return dict(id=window["kCGWindowNumber"], pid=window["kCGWindowOwnerPID"],
                            title=window["kCGWindowName"], bounds_kind="window_including_titlebar",
                            rectangle=[bounds["X"], bounds["Y"], bounds["X"] + bounds["Width"],
                                       bounds["Y"] + bounds["Height"]])
        return None
    if sys.platform.startswith("linux"):
        for pid in pids:
            search = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(pid)],
                                    capture_output=True, text=True, timeout=5)
            for handle in search.stdout.split():
                actual_title = subprocess.check_output(["xdotool", "getwindowname", handle], text=True).strip()
                if actual_title != title:
                    continue
                info = subprocess.check_output(["xwininfo", "-id", handle], text=True)
                if "Map State: IsViewable" not in info:
                    continue
                geometry = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", handle], text=True)
                values = dict(line.split("=", 1) for line in geometry.splitlines() if "=" in line)
                x, y, width, height = (int(values[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))
                if width > 0 and height > 0:
                    return dict(id=handle, pid=pid, title=actual_title,
                                rectangle=[x, y, x + width, y + height], bounds_kind="X11 client")
        return None
    raise RuntimeError("Unsupported host")


def prepare_window(window):
    """Place Windows clients inside the available desktop, above the taskbar."""
    if sys.platform != "win32":
        return
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    work = wintypes.RECT()
    if not user32.SystemParametersInfoW(48, 0, ctypes.byref(work), 0):
        raise RuntimeError("Cannot read Windows desktop work area")
    # SWP_NOSIZE | SWP_SHOWWINDOW. The source fixture supplies a 960x640 client.
    if not user32.SetWindowPos(window["id"], 0, work.left + 8, work.top + 8, 0, 0, 0x0041):
        raise RuntimeError("Cannot position owned window within desktop")
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow(window["id"])


def capture_once(window, path):
    if sys.platform == "darwin":
        import Quartz
        if hasattr(Quartz, "CGPreflightScreenCaptureAccess") and not Quartz.CGPreflightScreenCaptureAccess():
            raise RuntimeError("macOS screen-recording permission unavailable; no TCC prompt attempted")
        subprocess.run(["screencapture", "-x", "-o", "-l", str(window["id"]), str(path)],
                       check=True, timeout=15, capture_output=True)
    elif sys.platform.startswith("linux"):
        subprocess.run(["import", "-window", str(window["id"]), str(path)],
                       check=True, timeout=15, capture_output=True)
    else:
        from ctypes import wintypes
        work = wintypes.RECT()
        if not ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(work), 0):
            raise RuntimeError("Cannot verify desktop capture bounds")
        left, top, right, bottom = window["rectangle"]
        if left < work.left or top < work.top or right > work.right or bottom > work.bottom:
            raise RuntimeError(f"Client rectangle {window['rectangle']} extends outside desktop work area")
        ImageGrab.grab(bbox=tuple(window["rectangle"]), all_screens=True).save(path)
    with Image.open(path) as screenshot:
        # Exclude titlebar and outer borders: text in chrome must not make a black
        # GTK client count as rendered. This remains a heuristic, requiring review.
        content = screenshot.convert("RGB").crop((20, 60, screenshot.width - 20, screenshot.height - 20))
        if min(screenshot.size) < 100 or max(ImageStat.Stat(content).stddev) < 2:
            raise RuntimeError("Capture is too small or near-uniform; desktop rendering not established")
        return dict(width=screenshot.width, height=screenshot.height,
                    inspection="Nonuniform capture only; inspect PNG to confirm correct UI and no occlusion")


def capture(window, path, readiness_timeout=0):
    deadline = time.monotonic() + readiness_timeout
    attempts = 0
    while True:
        attempts += 1
        try:
            evidence = capture_once(window, path)
            evidence["readiness_attempts"] = attempts
            return evidence
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def summarize(rows):
    elapsed = rows[-1]["monotonic"] - rows[0]["monotonic"]
    # Count observed CPU increments, including newly discovered processes; exiting processes
    # lose their final fractional interval. Never subtract counters from different identities.
    previous = {f"{p['pid']}:{p['created']}": p["cpu_seconds"] for p in rows[0]["processes"]}
    total = 0.0
    late = set()
    for row in rows[1:]:
        for process in row["processes"]:
            identity = f"{process['pid']}:{process['created']}"
            current = process["cpu_seconds"]
            if identity not in previous and process["created"] <= rows[0].get("wall_time", -math.inf):
                # Its CPU at the baseline is unknown. Do not charge startup work
                # from before this phase to idle; refuse a complete CPU claim.
                late.add(identity)
                previous[identity] = current
            total += max(0, current - previous.get(identity, 0))
            previous[identity] = current
    memory = sorted(row["family_rss_bytes"] / 2**20 for row in rows[1:])
    return dict(seconds=elapsed, sample_intervals=len(rows) - 1,
                observed_cpu_seconds=total, late_discovered_preexisting_processes=sorted(late),
                observed_cpu_percent_one_core=100 * total / elapsed,
                family_rss_mib=dict(median=statistics.median(memory),
                                    p95=memory[math.ceil(.95 * len(memory)) - 1],
                                    observed_maximum=max(memory)))


def check_minimized(window):
    state = subprocess.check_output(["xprop", "-id", str(window["id"]), "_NET_WM_STATE"], text=True)
    info = subprocess.check_output(["xwininfo", "-id", str(window["id"])], text=True)
    if "_NET_WM_STATE_HIDDEN" not in state or "Map State: IsUnMapped" not in info:
        raise RuntimeError("Minimized state was not established by X11 state and map checks")


def phase(family, title, output, name, settle, seconds, minimized_window=None, client_size=None):
    end = time.monotonic() + settle
    while time.monotonic() < end:
        family.refresh()
        time.sleep(.2)
    if minimized_window:
        window = minimized_window
        check_minimized(window)
        evidence = {"state": "minimized verified with _NET_WM_STATE_HIDDEN and IsUnMapped"}
    else:
        window = find_window({p.pid for p in family.refresh()}, title)
        if not window:
            raise RuntimeError("No matching visible non-minimized window after settling")
        if client_size:
            left, top, right, bottom = window["rectangle"]
            if [right - left, bottom - top] != client_size:
                raise RuntimeError(f"Client size {[right-left, bottom-top]} differs from expected {client_size}")
        evidence = capture(window, output / f"{name}.png", readiness_timeout=45 if name == "diagnostic" else 0)
    rows = [family.sample()]
    write_json(output / f"{name}-samples.json", rows)
    for _ in range(seconds):
        # Poll ancestry at 5 Hz; record metrics at 1 Hz. Very short-lived children can escape.
        for _ in range(5):
            time.sleep(.2)
            family.refresh()
        rows.append(family.sample())
        write_json(output / f"{name}-samples.json", rows)
    if minimized_window:
        check_minimized(window)
    else:
        final_window = find_window({p.pid for p in family.refresh()}, title)
        if not final_window or final_window["id"] != window["id"]:
            raise RuntimeError("Window missing or replaced during sampling")
        if final_window["rectangle"] != window["rectangle"]:
            raise RuntimeError("Window geometry changed during sampling")
        capture(final_window, output / f"{name}-end.png")
    summary = summarize(rows)
    if summary["late_discovered_preexisting_processes"]:
        raise RuntimeError("Process predating CPU baseline was discovered late; complete idle CPU accounting unavailable")
    return dict(status="passed", window=window, capture=evidence, summary=summary)


def audit_scope(result, family, before_helpers):
    family.refresh()
    if family.external_scope:
        result["macos_process_scope"] = family.external_scope.report(require_webcontent=True)
        if not result["macos_process_scope"]["complete"] and result["status"] != "failed":
            result.update(status="incomplete_process_scope", reason="macOS WebKit responsibility scope validation failed")
    unassigned = {key: value for key, value in web_helpers().items()
                  if key not in before_helpers and value["pid"] not in family.known}
    result["unassigned_new_web_helpers"] = list(unassigned.values())
    if (unassigned or family.access_errors) and result["status"] in ("diagnostic_passed", "comparison_passed"):
        result.update(status="incomplete_process_scope", reason="Unattributed web helpers or denied process access after sampling")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", action="store_true")
    parser.add_argument("--client-size", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"),
                        help="Require physical client dimensions on Windows/Linux; unavailable for Quartz titlebar captures")
    parser.add_argument("--unsupported-reason")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = dict(name=args.name, status="failed", build_mode="release", environment=environment(),
                  memory_metric="Windows Working Set" if sys.platform == "win32" else ("macOS RSS" if sys.platform == "darwin" else "Linux RSS"),
                  limitations=["Summed RSS can double-count shared pages; this is not Linux PSS",
                               "Ancestry polled at 5 Hz; macOS responsibility scope at 1 Hz; short-lived children may escape",
                               "CPU may omit an exiting process's final interval; no system-service allocation",
                               "Idle UI only; minimized state measured only in an explicitly labeled Linux phase",
                               "Screenshot content and occlusion require artifact inspection"], phases={})
    family = None
    app = None
    result["cleanup_status"] = "not_needed"
    try:
        if args.unsupported_reason:
            result.update(status="not_run", reason=args.unsupported_reason)
            return 0
        if args.client_size and sys.platform == "darwin":
            raise RuntimeError("Quartz exposes outer bounds; client-size validation is Windows/Linux only")
        if not args.executable.is_file():
            raise RuntimeError("Release executable missing; inspect build log")
        before_helpers = web_helpers()
        command = [str(args.executable.resolve())]
        if sys.platform == "darwin" and args.name == "tauri":
            from macos_process_scope import launch_command
            command = launch_command(args.executable.resolve(), args.output)
        app_env = os.environ.copy()
        if sys.platform == "win32" and args.name == "gtk":
            runtime_path = Path("artifacts/build/windows-gtk-runtime.json")
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            app_env["PATH"] = runtime["path_prepend"] + os.pathsep + app_env["PATH"]
            app_env.update(runtime["environment"])
            result["runtime_variant"] = runtime
        with (args.output / "application.log").open("w", encoding="utf-8") as log:
            app = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=app_env)
            result["cleanup_status"] = "unknown"
            external_scope = None
            if sys.platform == "darwin" and args.name == "tauri":
                from macos_process_scope import MacOSProcessScope
                external_scope = MacOSProcessScope(psutil.Process(app.pid))
            family = Family(app.pid, external_scope=external_scope)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if app.poll() is not None:
                    raise RuntimeError(f"Application exited before window discovery: {app.returncode}")
                discovered = find_window({p.pid for p in family.refresh()}, args.title)
                if discovered:
                    prepare_window(discovered)
                    break
                time.sleep(.2)
            else:
                raise RuntimeError("No matching GUI window in 45s; GUI session/title visibility may be unavailable")
            result["phases"]["diagnostic"] = phase(family, args.title, args.output, "diagnostic", 5, 10,
                                                   client_size=args.client_size)
            unassigned = {key: value for key, value in web_helpers().items()
                          if key not in before_helpers and value["pid"] not in family.known}
            result["unassigned_new_web_helpers"] = list(unassigned.values())
            scope_complete = True
            if external_scope:
                result["macos_process_scope"] = external_scope.report(require_webcontent=True)
                scope_complete = result["macos_process_scope"]["complete"]
            if family.access_errors or unassigned or not scope_complete:
                result.update(status="incomplete_process_scope", reason="Unattributed web helpers, invalid responsibility scope or denied process access")
            else:
                result["status"] = "diagnostic_passed"
                if args.comparison:
                    result["phases"]["comparison"] = phase(family, args.title, args.output, "comparison", 30, 120,
                                                           client_size=args.client_size)
                    unassigned = {key: value for key, value in web_helpers().items()
                                  if key not in before_helpers and value["pid"] not in family.known}
                    result["unassigned_new_web_helpers"] = list(unassigned.values())
                    result["status"] = "comparison_passed" if not unassigned and not family.access_errors else "incomplete_process_scope"
                    if sys.platform.startswith("linux") and result["status"] == "comparison_passed":
                        window = result["phases"]["comparison"]["window"]
                        subprocess.run(["xdotool", "windowminimize", str(window["id"])], check=True, timeout=5)
                        result["phases"]["minimized"] = phase(
                            family, args.title, args.output, "minimized", 30, 120, minimized_window=window)
    except Exception as error:
        result.update(status="failed", reason=f"{type(error).__name__}: {error}")
    finally:
        if family:
            try:
                audit_scope(result, family, before_helpers)
            except Exception as error:
                result["scope_audit_error"] = f"{type(error).__name__}: {error}"
                if result["status"] != "failed":
                    result.update(status="incomplete_process_scope", reason="Final process scope audit failed")
            result["observed_processes"] = list(family.observed.values())
            try:
                result["cleanup_survivors"] = family.cleanup()
            except Exception as error:
                result["cleanup_survivors"] = "unknown"
                result["cleanup_error"] = f"{type(error).__name__}: {error}"
            result["process_access_denied_pids"] = sorted(family.access_errors)
            if family.access_errors and result["status"] in ("diagnostic_passed", "comparison_passed"):
                result.update(status="incomplete_process_scope", reason="Denied access to a tracked process")
            if result["cleanup_survivors"]:
                result.update(status="failed", reason="Tracked processes survived cleanup")
            elif (not family.access_errors and not result.get("unassigned_new_web_helpers")
                  and not result.get("scope_audit_error")
                  and result.get("macos_process_scope", {}).get("complete", True)):
                result["cleanup_status"] = "clean"
        elif app:
            # Construction of the family tracker failed after launch. Reap the root,
            # but retain unknown cleanup because its descendants were not observed.
            try:
                app.terminate()
                app.wait(timeout=3)
            except Exception:
                result["cleanup_error"] = "Root cleanup failed after family tracker initialization failure"
        write_json(args.output / "outcome.json", result)
        print(json.dumps(dict(name=args.name, status=result["status"], reason=result.get("reason"))))
    return 0 if result["status"] in ("diagnostic_passed", "comparison_passed") else 1


if __name__ == "__main__":
    sys.exit(main())
