#!/usr/bin/env python3
"""Verify one example's shell-integration checks from outside the application.

The example is built with its shell-checks option and started with
COMPARISON_SHELL_CHECKS=1. It sets up a tray icon, a Dock/taskbar badge, a global
shortcut (Ctrl+Alt+Shift+F9), single-instance handling and, after a delay, an
attention request, and reports each step as a `SHELL {json}` line. This probe then
looks for the effect where the operating system exposes it:

  tray       Linux: StatusNotifierItem registration and a D-Bus Activate click;
             macOS: a status-bar window (layer 25) owned by the app;
             Windows: a notification-area toolbar button owned by the app, then a
             real mouse click on it (the workflow shows all icons, EnableAutoTray=0)
  badge      macOS: the Dock tile label (lsappinfo StatusLabel);
             Linux: a com.canonical.Unity.LauncherEntry signal; Windows: not observable
  hotkey     a synthetic key press (xdotool / keybd_event / System Events) must reach the app
  single     a second launch must exit; forwarding to the first is recorded separately
  attention  Linux X11 (focus moved to another window): urgency hint or
             _NET_WM_STATE_DEMANDS_ATTENTION; Windows (window minimized):
             an HSHELL_FLASH shell-hook message; macOS: not observable

Each check gets a verdict: pass (effect observed), api-only (the app reported success
but the OS gives no outside view), no-api (the framework has no API; not built with a
workaround), fail (error or effect absent) or not-run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

ATTENTION_DELAY = 50  # seconds after setup; must exceed the checks before it
TOOLTIP = "Veranda shell check"
NO_API = ("no-api",)
FAILED = ("error", "no-host")


def run(command, timeout=20, **kwargs):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(command, -1, "", str(error))


class App:
    """A launched example whose stdout is parsed for SHELL lines."""

    def __init__(self, command, env, log_path: Path):
        self.lines: list[tuple[float, dict | None, str]] = []
        self.log = log_path.open("w", encoding="utf-8", errors="replace")
        self.started = time.monotonic()
        self.proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for raw in self.proc.stdout:
            text = raw.decode("utf-8", "replace").rstrip("\r\n")
            self.log.write(text + "\n")
            self.log.flush()
            entry = None
            if text.startswith("SHELL "):
                try:
                    entry = json.loads(text[6:])
                except ValueError:
                    pass
            self.lines.append((time.monotonic(), entry, text))

    def events(self, check=None, status=None, since=0.0):
        statuses = (status,) if isinstance(status, str) else status
        return [e for t, e, _ in list(self.lines)
                if e and t >= since and (check is None or e.get("check") == check)
                and (statuses is None or e.get("status") in statuses)]

    def wait_for(self, check, status=None, timeout=10.0, since=0.0):
        deadline = time.monotonic() + timeout
        while True:
            found = self.events(check, status, since)
            if found:
                return found[0]
            if time.monotonic() > deadline or self.proc.poll() is not None:
                time.sleep(0.3)
                found = self.events(check, status, since)
                return found[0] if found else None
            time.sleep(0.1)

    def pids(self):
        try:
            root = psutil.Process(self.proc.pid)
            return {root.pid, *(child.pid for child in root.children(recursive=True))}
        except psutil.NoSuchProcess:
            return set()

    def stop(self):
        stop_tree(self.proc)
        self.log.close()


def stop_tree(proc):
    try:
        root = psutil.Process(proc.pid)
        family = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        family = []
    for process in reversed(family):
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(family, timeout=5)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


# ---------------------------------------------------------------- Linux (X11, D-Bus)

def linux_window(pids):
    best, best_area = None, 0
    for pid in pids:
        for wid in run(["xdotool", "search", "--onlyvisible", "--pid", str(pid)]).stdout.split():
            values = dict(line.split("=", 1) for line in
                          run(["xdotool", "getwindowgeometry", "--shell", wid]).stdout.splitlines() if "=" in line)
            area = int(values.get("WIDTH", 0)) * int(values.get("HEIGHT", 0))
            if area > best_area:
                best, best_area = wid, area
    return best


def bus_pid(name):
    out = run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path",
               "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.GetConnectionUnixProcessID", name]).stdout
    match = re.search(r"uint32 (\d+)", out)
    return int(match.group(1)) if match else None


def linux_tray(app, watcher_log: Path, offset: int):
    text = watcher_log.read_text(encoding="utf-8", errors="replace")[offset:] if watcher_log.exists() else ""
    pids = app.pids()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[0] != "REGISTER":
            continue
        _, sender, argument = parts
        if bus_pid(sender) in pids:
            service = sender if argument.startswith("/") else argument
            path = argument if argument.startswith("/") else "/StatusNotifierItem"
            return dict(observed=True, how=f"StatusNotifierItem registered: {sender} {argument}",
                        service=service, path=path)
    return dict(observed=False, how="no StatusNotifierItem registration from the app's processes",
                watcher_log=text[-2000:])


def linux_click(app, tray):
    since = time.monotonic()
    call = run(["gdbus", "call", "--session", "--dest", tray["service"], "--object-path", tray["path"],
                "--method", "org.kde.StatusNotifierItem.Activate", "0", "0"])
    event = app.wait_for("tray", "click", timeout=4, since=since)
    return dict(clicked=bool(event), how="D-Bus StatusNotifierItem.Activate",
                call=(call.stdout + call.stderr).strip()[:500])


def linux_badge(monitor_log: Path, offset: int):
    text = monitor_log.read_text(encoding="utf-8", errors="replace")[offset:] if monitor_log.exists() else ""
    seen = "LauncherEntry" in text and "count" in text
    return dict(observed=seen, how="com.canonical.Unity.LauncherEntry Update signal" if seen
                else "no LauncherEntry signal on the session bus", excerpt=text[-1500:])


def linux_attention(wid):
    hints = run(["xprop", "-id", wid, "-notype", "-f", "WM_HINTS", "32i", " $0\n", "WM_HINTS"]).stdout
    state = run(["xprop", "-id", wid, "-notype", "_NET_WM_STATE"]).stdout
    match = re.search(r"WM_HINTS\s+(-?\d+)", hints)
    urgency = bool(match and int(match.group(1)) & 256)
    demands = "_NET_WM_STATE_DEMANDS_ATTENTION" in state
    return dict(observed=urgency or demands, urgency_hint=urgency, demands_attention=demands,
                how="X11 WM_HINTS urgency / _NET_WM_STATE", raw=(hints + state).strip()[:500])


# ---------------------------------------------------------------- Windows

class ShellHook:
    """Hidden top-level window registered for shell-hook messages (HSHELL_FLASH)."""

    def __init__(self):
        self.events: list[tuple[float, int, int]] = []
        self.ready = threading.Event()
        self.error = None
        threading.Thread(target=self._run, daemon=True).start()
        self.ready.wait(5)

    def _run(self):
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        lresult = ctypes.c_ssize_t
        wndproc_type = ctypes.WINFUNCTYPE(lresult, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = lresult
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        shell_message = user32.RegisterWindowMessageW("SHELLHOOK")

        def procedure(hwnd, message, wparam, lparam):
            if message == shell_message:
                self.events.append((time.monotonic(), int(wparam), int(lparam or 0)))
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self._procedure = wndproc_type(procedure)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", wndproc_type), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        instance = kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSW(lpfnWndProc=self._procedure, hInstance=instance, lpszClassName="ShellProbeHook")
        user32.RegisterClassW(ctypes.byref(window_class))
        hwnd = user32.CreateWindowExW(0, "ShellProbeHook", "shell probe", 0, 0, 0, 0, 0, None, None, instance, None)
        if not hwnd or not user32.RegisterShellHookWindow(hwnd):
            self.error = f"shell hook registration failed: {ctypes.GetLastError()}"
            self.ready.set()
            return
        self.ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

    def flashes(self, pids, since):
        import ctypes
        from ctypes import wintypes
        found = []
        for t, code, hwnd in list(self.events):
            if t < since or code != 0x8006:  # HSHELL_FLASH
                continue
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
            if pid.value in pids:
                found.append(hwnd)
        return found


def windows_top_level(pids):
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return found


def windows_tray_buttons(pids):
    """Read the notification-area toolbars inside Explorer.

    Each button's data is a TRAYDATA record whose first field is the icon owner's
    window; its process tells which app the icon belongs to.
    """
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.FindWindowExW.restype = wintypes.HWND
    user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.POINTER(ctypes.c_size_t)]

    def child(parent, cls):
        return user32.FindWindowExW(parent, None, cls, None)

    tray = child(None, "Shell_TrayWnd")
    pager = child(child(tray, "TrayNotifyWnd"), "SysPager") if tray else None
    toolbars = [("promoted", child(pager, "ToolbarWindow32") if pager else None),
                ("overflow", child(child(None, "NotifyIconOverflowWindow"), "ToolbarWindow32"))]
    buttons = []
    for area, toolbar in toolbars:
        if not toolbar:
            continue
        explorer = wintypes.DWORD()
        user32.GetWindowThreadProcessId(toolbar, ctypes.byref(explorer))
        process = kernel32.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, explorer.value)
        if not process:
            continue
        remote = kernel32.VirtualAllocEx(process, None, 4096, 0x1000, 0x04)
        try:
            for index in range(user32.SendMessageW(toolbar, 0x418, 0, 0)):  # TB_BUTTONCOUNT
                raw = (ctypes.c_ubyte * 32)()
                user32.SendMessageW(toolbar, 0x417, index, remote)  # TB_GETBUTTON
                kernel32.ReadProcessMemory(process, remote, raw, 32, None)
                data = int.from_bytes(bytes(raw[16:24]), "little")
                record = (ctypes.c_ubyte * 16)()
                if not data or not kernel32.ReadProcessMemory(process, ctypes.c_void_p(data), record, 16, None):
                    continue
                owner = int.from_bytes(bytes(record[0:8]), "little")
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(wintypes.HWND(owner), ctypes.byref(pid))
                rect = wintypes.RECT()
                user32.SendMessageW(toolbar, 0x41D, index, remote)  # TB_GETITEMRECT
                kernel32.ReadProcessMemory(process, remote, ctypes.byref(rect), ctypes.sizeof(rect), None)
                corner = wintypes.POINT(rect.left, rect.top)
                user32.ClientToScreen(toolbar, ctypes.byref(corner))
                buttons.append(dict(area=area, pid=pid.value, ours=pid.value in pids,
                                    center=[corner.x + (rect.right - rect.left) // 2,
                                            corner.y + (rect.bottom - rect.top) // 2]))
        finally:
            kernel32.VirtualFreeEx(process, ctypes.c_void_p(remote), 0, 0x8000)
            kernel32.CloseHandle(process)
    return buttons


def windows_click(point):
    import ctypes
    user32 = ctypes.windll.user32
    user32.SetCursorPos(*point)
    time.sleep(0.3)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
    time.sleep(0.5)
    user32.keybd_event(0x1B, 0, 0, 0)  # Escape closes a menu opened by the click
    user32.keybd_event(0x1B, 0, 2, 0)


def windows_hotkey():
    import ctypes
    user32 = ctypes.windll.user32
    keys = (0x11, 0x12, 0x10, 0x78)  # Ctrl, Alt, Shift, F9
    for key in keys:
        user32.keybd_event(key, 0, 0, 0)
    for key in reversed(keys):
        user32.keybd_event(key, 0, 2, 0)  # KEYEVENTF_KEYUP
    return "keybd_event Ctrl+Alt+Shift+F9"


# ---------------------------------------------------------------- macOS

def macos_status_windows(pids):
    import Quartz
    windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID) or []
    found = []
    for window in windows:
        if int(window.get("kCGWindowOwnerPID", -1)) in pids and int(window.get("kCGWindowLayer", 0)) == 25:
            bounds = window.get("kCGWindowBounds", {})
            found.append(dict(layer=25, bounds={k: float(v) for k, v in bounds.items()}))
    return found


def macos_badge(pid):
    asn = run(["lsappinfo", "find", f"pid={pid}"]).stdout.strip()
    info = run(["lsappinfo", "info", "-only", "StatusLabel", asn]).stdout.strip() if asn else ""
    label = re.search(r'"label"="([^"]*)"', info)
    return dict(observed=bool(label and label.group(1)), how="lsappinfo StatusLabel (Dock tile badge)",
                asn=asn, raw=info[:300])


def macos_hotkey():
    script = 'tell application "System Events" to key code 101 using {control down, option down, shift down}'
    result = run(["osascript", "-e", script])
    return "System Events key code 101" + ("" if result.returncode == 0 else f" failed: {result.stderr.strip()[:300]}")


# ---------------------------------------------------------------- common

def screenshot(path: Path):
    if sys.platform.startswith("linux"):
        run(["import", "-window", "root", str(path)])
    elif sys.platform == "darwin":
        run(["screencapture", "-x", str(path)])
    else:
        from PIL import ImageGrab
        ImageGrab.grab(all_screens=True).save(path)


def verdict(app_event, observed, no_api_ok=True):
    if app_event is None:
        return "fail"
    if app_event["status"] in NO_API:
        return "no-api"
    if app_event["status"] in FAILED:
        return "fail"
    if observed is None:
        return "api-only"
    return "pass" if observed else "fail"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    linux, windows, macos = sys.platform.startswith("linux"), sys.platform == "win32", sys.platform == "darwin"
    result = dict(name=args.name, platform=sys.platform, executable=str(args.executable), checks={})
    checks = result["checks"]
    out_path = args.output / "result.json"

    def save():
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if not args.executable.is_file():
        result["error"] = "executable missing; see the build log"
        save()
        return 1
    env = os.environ.copy()
    env["COMPARISON_SHELL_CHECKS"] = "1"
    env["COMPARISON_SHELL_ATTENTION_DELAY"] = str(ATTENTION_DELAY)
    if windows and args.name == "gtk":
        runtime = json.loads(Path("artifacts/build/windows-gtk-runtime.json").read_text(encoding="utf-8"))
        env["PATH"] = runtime["path_prepend"] + os.pathsep + env["PATH"]
        env.update(runtime["environment"])
    command = [str(args.executable.resolve())]
    hook = ShellHook() if windows else None
    if hook and hook.error:
        result["shell_hook_error"] = hook.error
    watcher_log = Path(os.environ.get("SNI_WATCHER_LOG", "/nonexistent"))
    monitor_log = Path(os.environ.get("LAUNCHER_MONITOR_LOG", "/nonexistent"))
    watcher_offset = len(watcher_log.read_text(errors="replace")) if watcher_log.exists() else 0
    monitor_offset = len(monitor_log.read_text(errors="replace")) if monitor_log.exists() else 0

    app = App(command, env, args.output / "application.log")
    try:
        for check in ("tray", "hotkey", "badge"):
            app.wait_for(check, timeout=60)
        if app.proc.poll() is not None:
            result["error"] = f"application exited early with {app.proc.returncode}"
            return 1
        time.sleep(3)
        screenshot(args.output / "running.png")

        # Tray icon
        event = app.events("tray", ("created", "error", "no-host"))
        event = event[0] if event else None
        tray = dict(app=event)
        if event and event["status"] == "created":
            if linux:
                tray.update(linux_tray(app, watcher_log, watcher_offset))
                if tray["observed"]:
                    tray.update(linux_click(app, tray))
            elif macos:
                found = macos_status_windows(app.pids())
                tray.update(observed=bool(found), how="status-bar window (layer 25) owned by the app",
                            windows=found)
            else:
                buttons = windows_tray_buttons(app.pids())
                ours = [b for b in buttons if b["ours"]]
                tray.update(observed=bool(ours), how="notification-area toolbar button owned by the app",
                            buttons=buttons)
                promoted = [b for b in ours if b["area"] == "promoted"]
                if promoted:
                    since = time.monotonic()
                    windows_click(promoted[0]["center"])
                    tray["clicked"] = bool(app.wait_for("tray", "click", timeout=4, since=since))
                    tray["click_how"] = "left mouse click on the icon"
        tray["verdict"] = verdict(event, tray.get("observed"))
        checks["tray"] = tray

        # Badge
        event = app.events("badge")
        event = event[0] if event else None
        badge = dict(app=event)
        if event and event["status"] == "set":
            if macos:
                badge.update(macos_badge(app.proc.pid))
            elif linux:
                badge.update(linux_badge(monitor_log, monitor_offset))
            else:
                badge.update(observed=None, how="taskbar overlay icons are not exposed to other processes")
        badge["verdict"] = verdict(event, badge.get("observed"))
        checks["badge"] = badge

        # Global shortcut
        event = app.events("hotkey", ("registered", "error", "no-api"))
        event = event[0] if event else None
        hotkey = dict(app=event)
        if event and event["status"] == "registered":
            since = time.monotonic()
            if linux:
                hotkey["injected"] = "xdotool key " + run(["xdotool", "key", "ctrl+alt+shift+F9"]).stderr.strip()
            elif windows:
                hotkey["injected"] = windows_hotkey()
            else:
                hotkey["injected"] = macos_hotkey()
            received = app.wait_for("hotkey", "event", timeout=5, since=since)
            hotkey["observed"] = bool(received)
        hotkey["verdict"] = verdict(event, hotkey.get("observed"))
        checks["hotkey"] = hotkey

        # Single instance
        event = app.events("single-instance", ("primary", "remote", "error"))
        event = event[0] if event else None
        single = dict(app=event)
        since = time.monotonic()
        second = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        try:
            output, _ = second.communicate(timeout=25)
            single.update(second_exited=True, second_exit_code=second.returncode,
                          second_seconds=round(time.monotonic() - since, 2))
        except subprocess.TimeoutExpired:
            stop_tree(second)
            output, _ = second.communicate(timeout=10)
            single.update(second_exited=False, how="second launch was still running after 25 s")
        (args.output / "second-instance.log").write_bytes(output or b"")
        single["forwarded"] = bool(app.wait_for("single-instance", "forwarded", timeout=5, since=since))
        single["observed"] = bool(single.get("second_exited") and single.get("second_exit_code") == 0)
        single["verdict"] = verdict(event or dict(status="unreported"), single["observed"])
        checks["single_instance"] = single

        # Attention: minimize first so the request reaches an inactive window.
        attention = {}
        focus = None
        if linux:
            # Activate another window instead of minimizing: Qt does not mark an
            # unmapped (iconified) window as demanding attention.
            attention["window"] = linux_window(app.pids())
            focus = subprocess.Popen(["xmessage", "-geometry", "+1200+820", "focus holder"])
            # xmessage sets no _NET_WM_PID, so find it by its WM_CLASS.
            holder = run(["xdotool", "search", "--sync", "--onlyvisible", "--classname", "xmessage"],
                         timeout=10).stdout.split()
            if holder:
                run(["xdotool", "windowactivate", "--sync", holder[0]])
            attention["deactivated"] = "focus moved to another window" if holder else "no focus holder"
        elif windows:
            import ctypes
            for hwnd in windows_top_level(app.pids()):
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            attention["deactivated"] = "window minimized"
        remaining = ATTENTION_DELAY + 20 - (time.monotonic() - app.started)
        event = app.wait_for("attention", timeout=max(remaining, 5))
        attention["app"] = event
        if event and event["status"] == "requested":
            time.sleep(2)
            if linux and attention.get("window"):
                attention.update(linux_attention(attention["window"]))
            elif windows and hook and not hook.error:
                flashes = hook.flashes(app.pids(), app.started)
                attention.update(observed=bool(flashes), how="HSHELL_FLASH shell-hook message", windows=flashes)
            else:
                attention.update(observed=None, how="Dock bounce is not exposed to other processes")
        attention["verdict"] = verdict(event, attention.get("observed"))
        checks["attention"] = attention
        if focus:
            focus.terminate()
        return 0
    finally:
        result["exit_code"] = app.proc.poll()
        app.stop()
        result["shell_lines"] = [entry for _, entry, _ in app.lines if entry]
        save()


if __name__ == "__main__":
    sys.exit(main())
