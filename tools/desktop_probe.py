#!/usr/bin/env python3
"""External desktop acceptance checks for a disposable, otherwise idle session.

These checks change the OS appearance and replace the clipboard with synthetic
text. Never run them on a user's working desktop. The original appearance is
restored; arbitrary clipboard formats/ownership are deliberately not captured or
restored. All probe-owned clipboard helper processes are stopped.

The ordinary filter widget is exercised through Ctrl/Cmd+F and platform keyboard
input. No application clipboard API, test backdoor, or same-process clipboard
round trip is used. Native Wayland input injection is not implemented here: X11
checks must not be presented as native Wayland coverage.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from PIL import Image, ImageStat


class DesktopEnvironmentError(RuntimeError):
    """A host prerequisite failed before framework behavior could be tested."""


def command(args, *, input=None, timeout=10, check=True):
    try:
        result = subprocess.run(args, input=input, capture_output=True, text=True,
                                encoding="utf-8", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DesktopEnvironmentError(f"{args[0]} unavailable or timed out: {error}") from error
    if check and result.returncode:
        raise DesktopEnvironmentError(
            f"{args[0]} exited {result.returncode}: {result.stderr.strip()[:500]}")
    return result


def portal_color_scheme(text):
    """Decode gdbus' uint32 variant, refusing unrelated or unsupported values."""
    match = re.fullmatch(r"\s*\(<(?:uint32\s+)?([012])>,?\)\s*", text)
    if not match:
        raise DesktopEnvironmentError(f"Unexpected Settings portal reply: {text.strip()!r}")
    return int(match.group(1))


class SystemTheme:
    """Set a real OS preference, notify subscribers, and independently read it."""

    def __init__(self):
        self.saved = None

    def snapshot(self):
        if sys.platform.startswith("linux"):
            self.saved = {key: command(["gsettings", "get", "org.gnome.desktop.interface", key]).stdout.strip()
                          for key in ("color-scheme", "gtk-theme")}
        elif sys.platform == "win32":
            import winreg
            self.saved = {"AppsUseLightTheme": None, "SystemUsesLightTheme": None}
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path())
            except FileNotFoundError:
                # A fresh runner may have no Personalize key. Absence means OS
                # defaults, not an inability to change the appearance preference.
                return
            with key:
                for name in self.saved:
                    try:
                        self.saved[name] = winreg.QueryValueEx(key, name)
                    except FileNotFoundError:
                        pass
        elif sys.platform == "darwin":
            value = command(["defaults", "read", "-g", "AppleInterfaceStyle"], check=False)
            self.saved = {"dark": value.returncode == 0 and value.stdout.strip() == "Dark"}
        else:
            raise DesktopEnvironmentError(f"Unsupported desktop host: {sys.platform}")

    @staticmethod
    def registry_path():
        return r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

    @staticmethod
    def notify_windows():
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                               wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                               ctypes.POINTER(ctypes.c_size_t)]
        user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        name = ctypes.create_unicode_buffer("ImmersiveColorSet")
        result = ctypes.c_size_t()
        # WM_SETTINGCHANGE / HWND_BROADCAST, bounded even if another window hangs.
        ok = user32.SendMessageTimeoutW(0xffff, 0x001a, 0, ctypes.addressof(name),
                                       0x0002, 2000, ctypes.byref(result))
        if not ok:
            raise DesktopEnvironmentError("Windows appearance-change broadcast failed")

    def read(self):
        if sys.platform.startswith("linux"):
            prefix = ["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
                      "--object-path", "/org/freedesktop/portal/desktop", "--method"]
            result = command(prefix + ["org.freedesktop.portal.Settings.ReadOne",
                                       "org.freedesktop.appearance", "color-scheme"], check=False)
            # Older portal versions expose Read, whose returned variant may be nested.
            if result.returncode and "UnknownMethod" in result.stderr:
                result = command(prefix + ["org.freedesktop.portal.Settings.Read",
                                           "org.freedesktop.appearance", "color-scheme"])
                value = result.stdout.replace("<<", "<").replace(">>", ">")
            elif result.returncode:
                raise DesktopEnvironmentError(f"Settings portal unavailable: {result.stderr.strip()[:500]}")
            else:
                value = result.stdout
            scheme = portal_color_scheme(value)
            legacy = command(["gtk-query-settings", "gtk-theme-name"]).stdout.strip()
            match = re.fullmatch(r'gtk-theme-name:\s*"([^"\r\n]+)"', legacy)
            if not match:
                raise DesktopEnvironmentError(f"Unexpected GTK/XSettings theme reply: {legacy!r}")
            gtk_theme = match.group(1)
            expected = {1: "Adwaita-dark", 2: "Adwaita"}.get(scheme)
            if expected and gtk_theme != expected:
                raise DesktopEnvironmentError(
                    f"Portal scheme {scheme} and effective GTK/XSettings theme {gtk_theme!r} are inconsistent; expected {expected!r}")
            return dict(source="org.freedesktop.portal.Settings", value=scheme,
                        theme={0: "no-preference", 1: "dark", 2: "light"}[scheme], gtk_theme=gtk_theme,
                        gtk_theme_source="gtk-query-settings via the session XSettings provider",
                        session_profile="gnome-adwaita-dual-preference-v1")
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path()) as key:
                value = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
            return dict(source="HKCU AppsUseLightTheme", value=value,
                        theme="light" if value else "dark")
        value = command(["defaults", "read", "-g", "AppleInterfaceStyle"], check=False)
        dark = value.returncode == 0 and value.stdout.strip() == "Dark"
        return dict(source="NSGlobalDomain AppleInterfaceStyle", value="Dark" if dark else None,
                    theme="dark" if dark else "light")

    def set(self, theme):
        if theme not in ("light", "dark"):
            raise ValueError(f"Invalid system theme: {theme}")
        if sys.platform.startswith("linux"):
            # A complete session publishes both modern color preference and the
            # legacy GTK3/XSettings theme used by Qt's GTK platform integration.
            # This shared, explicitly named profile applies to every candidate;
            # it is not a per-application palette or GTK_THEME override.
            gtk_theme = "Adwaita-dark" if theme == "dark" else "Adwaita"
            command(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", gtk_theme])
            command(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", f"prefer-{theme}"])
        elif sys.platform == "win32":
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.registry_path()) as key:
                for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(theme == "light"))
            self.notify_windows()
        elif sys.platform == "darwin":
            # This is the OS appearance preference setter, not app-specific styling.
            # A denied Automation permission is a host error, never a framework fail.
            command(["osascript", "-e", 'tell application "System Events" to tell appearance preferences '
                     f'to set dark mode to {str(theme == "dark").lower()}'], timeout=10)
        else:
            raise DesktopEnvironmentError(f"Unsupported desktop host: {sys.platform}")
        deadline = time.monotonic() + 8
        while True:
            try:
                setting = self.read()
                if setting["theme"] == theme:
                    return setting
                last_error = f"OS preference did not become {theme}: {setting}"
            except DesktopEnvironmentError as error:
                # Portal activation can race the first read in a fresh session.
                # Keep the wait bounded, and preserve the last prerequisite error.
                last_error = str(error)
            if time.monotonic() >= deadline:
                raise DesktopEnvironmentError(last_error)
            time.sleep(.2)

    def restore(self):
        if self.saved is None:
            return
        if sys.platform.startswith("linux"):
            errors = []
            for key, value in self.saved.items():
                try:
                    command(["gsettings", "set", "org.gnome.desktop.interface", key, value])
                except DesktopEnvironmentError as error:
                    errors.append(f"{key}: {error}")
            if errors:
                raise DesktopEnvironmentError("Linux appearance restoration failed: " + "; ".join(errors))
        elif sys.platform == "win32":
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.registry_path()) as key:
                for name, old in self.saved.items():
                    if old is None:
                        try:
                            winreg.DeleteValue(key, name)
                        except FileNotFoundError:
                            pass
                    else:
                        value, kind = old
                        winreg.SetValueEx(key, name, 0, kind, value)
            self.notify_windows()
        else:
            self.set("dark" if self.saved["dark"] else "light")


class Clipboard:
    """System clipboard owned/read by this external probe, not the application."""

    def __init__(self):
        self.owners = []
        self.window_handle = None

    def pump_windows_messages(self, user32):
        """Service ownership notifications on the thread that created our HWND.

        EmptyClipboard in the application can synchronously send
        WM_DESTROYCLIPBOARD to our previous owner. PeekMessage also dispatches
        pending sent messages, even when it finds no queued message. Without
        this pump, the app can block waiting for us while we retry OpenClipboard.
        Only this probe's message-only HWND is addressed; there is no extra UI.
        """
        from ctypes import wintypes
        pointer = ctypes.POINTER(wintypes.MSG)
        user32.PeekMessageW.argtypes = [pointer, wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        user32.PeekMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [pointer]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [pointer]
        user32.DispatchMessageW.restype = ctypes.c_ssize_t  # LRESULT is pointer-sized on Win64.
        message = wintypes.MSG()
        deadline = time.monotonic() + .025
        for _ in range(64):
            if not user32.PeekMessageW(ctypes.byref(message), self.window_handle, 0, 0, 0x0001):  # PM_REMOVE
                return
            if message.message == 0x0012:  # WM_QUIT should not be swallowed.
                raise DesktopEnvironmentError("Clipboard probe message queue requested shutdown")
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
            if time.monotonic() >= deadline:
                return

    def windows_api(self):
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        if self.window_handle is None:
            # EmptyClipboard needs a real owner HWND before SetClipboardData.
            # A message-only STATIC window avoids any visible probe UI.
            user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                               wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                               ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                               wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
            user32.CreateWindowExW.restype = wintypes.HWND
            self.window_handle = user32.CreateWindowExW(
                0, "STATIC", "Desktop clipboard probe", 0, 0, 0, 0, 0, -3, None, None, None)
            if not self.window_handle:
                raise DesktopEnvironmentError("Cannot create clipboard owner window")
        deadline = time.monotonic() + 3
        while True:
            self.pump_windows_messages(user32)
            if user32.OpenClipboard(self.window_handle):
                break
            if time.monotonic() >= deadline:
                raise DesktopEnvironmentError("System clipboard remained locked")
            time.sleep(.05)
        return user32, kernel32

    def write(self, text):
        if sys.platform.startswith("linux"):
            # Foreground ownership avoids an untracked xclip daemon. Replacing the
            # selection causes this helper to exit; any survivor is reaped in close().
            try:
                owner = subprocess.Popen(["xclip", "-selection", "clipboard", "-in", "-quiet"],
                                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
            except OSError as error:
                raise DesktopEnvironmentError(f"Cannot start X11 clipboard helper: {error}") from error
            self.owners.append(owner)
            try:
                owner.stdin.write(text.encode("utf-8"))
                owner.stdin.close()
            except OSError as error:
                raise DesktopEnvironmentError(f"X11 clipboard helper could not accept text: {error}") from error
        elif sys.platform == "darwin":
            command(["pbcopy"], input=text)
        elif sys.platform == "win32":
            user32, kernel32 = self.windows_api()
            handle = None
            try:
                data = text.encode("utf-16-le") + b"\0\0"
                handle = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
                if not handle:
                    raise DesktopEnvironmentError("GlobalAlloc for clipboard failed")
                address = kernel32.GlobalLock(handle)
                if not address:
                    raise DesktopEnvironmentError("GlobalLock for clipboard failed")
                ctypes.memmove(address, data, len(data))
                kernel32.GlobalUnlock(handle)
                if not user32.EmptyClipboard() or not user32.SetClipboardData(13, handle):
                    raise DesktopEnvironmentError("SetClipboardData(CF_UNICODETEXT) failed")
                handle = None  # ownership transferred to the OS
            finally:
                if handle:
                    kernel32.GlobalFree(handle)
                user32.CloseClipboard()
        else:
            raise DesktopEnvironmentError(f"Unsupported clipboard host: {sys.platform}")
        deadline = time.monotonic() + 3
        while self.read() != text:
            if time.monotonic() >= deadline:
                raise DesktopEnvironmentError("External clipboard seed could not be read back")
            time.sleep(.05)

    def read(self):
        if sys.platform.startswith("linux"):
            return command(["xclip", "-selection", "clipboard", "-out"], check=False).stdout
        if sys.platform == "darwin":
            return command(["pbpaste"]).stdout
        if sys.platform == "win32":
            user32, kernel32 = self.windows_api()
            try:
                handle = user32.GetClipboardData(13)
                if not handle:
                    return None
                address = kernel32.GlobalLock(handle)
                if not address:
                    raise DesktopEnvironmentError("Cannot lock system clipboard text")
                try:
                    return ctypes.wstring_at(address)
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
        raise DesktopEnvironmentError(f"Unsupported clipboard host: {sys.platform}")

    def close(self):
        for owner in self.owners:
            if owner.poll() is None:
                owner.terminate()
            try:
                owner.wait(timeout=2)
            except subprocess.TimeoutExpired:
                owner.kill()
                owner.wait(timeout=2)
        self.owners.clear()
        if self.window_handle is not None:
            from ctypes import wintypes
            ctypes.windll.user32.DestroyWindow.argtypes = [wintypes.HWND]
            if not ctypes.windll.user32.DestroyWindow(self.window_handle):
                raise DesktopEnvironmentError("Cannot destroy probe clipboard owner window")
            self.window_handle = None


class DesktopInput:
    """Real platform keyboard input into the focused native window."""

    @staticmethod
    def macos_frontmost_pid():
        """Read the key-event recipient in an isolated, read-only native helper.

        NSWorkspace.frontmostApplication is Apple's documented key-event
        recipient. A fresh process avoids AppKit's run-loop-dependent caches
        and does not initialize or activate an NSApplication in this probe.
        https://developer.apple.com/documentation/appkit/nsworkspace/frontmostapplication
        """
        script = ("ObjC.import('AppKit'); "
                  "var front = $.NSWorkspace.sharedWorkspace.frontmostApplication; "
                  "front.isNil() ? 0 : front.processIdentifier")
        observed = command(["osascript", "-l", "JavaScript", "-e", script], timeout=2).stdout.strip()
        if not re.fullmatch(r"[1-9][0-9]*", observed):
            raise DesktopEnvironmentError(f"Invalid NSWorkspace frontmost PID: {observed!r}")
        return observed

    @staticmethod
    def macos_activation_click(window):
        """Make one normal titlebar click on a freshly verified, exposed window.

        This is only an activation request on a disposable test desktop. Refuse
        permission denial, stale ownership and occlusion rather than clicking a
        different application or treating a posted event as proof of focus.
        """
        import Quartz
        if not hasattr(Quartz, "CGPreflightPostEventAccess") or not Quartz.CGPreflightPostEventAccess():
            raise DesktopEnvironmentError("macOS mouse event-posting permission unavailable; no TCC prompt attempted")
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID) or []
        candidates = [(index, item) for index, item in enumerate(windows)
                      if item.get("kCGWindowNumber") == window["id"] and item.get("kCGWindowOwnerPID") == window["pid"]
                      and item.get("kCGWindowLayer") == 0]
        if len(candidates) != 1:
            raise DesktopEnvironmentError("Cannot locate the exact owned macOS window for activation click")
        index, target = candidates[0]
        bounds = target.get("kCGWindowBounds", {})
        values = [bounds.get(key) for key in ("X", "Y", "Width", "Height")]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in values):
            raise DesktopEnvironmentError("Invalid macOS window bounds for activation click")
        left, top, width, height = values
        if width < 200 or height < 100:
            raise DesktopEnvironmentError("macOS window is too small for a safe titlebar activation click")
        point = (left + width / 2, top + 12)
        # Quartz's on-screen list is ordered front-to-back. Do not send input
        # through another visible window, including menus or transient dialogs.
        for item in windows[:index]:
            other = item.get("kCGWindowBounds", {})
            if item.get("kCGWindowAlpha", 1) > 0 and all(key in other for key in ("X", "Y", "Width", "Height")) \
                    and other["X"] <= point[0] < other["X"] + other["Width"] \
                    and other["Y"] <= point[1] < other["Y"] + other["Height"]:
                blocker = dict(window_id=item.get("kCGWindowNumber"), pid=item.get("kCGWindowOwnerPID"),
                               owner_name=item.get("kCGWindowOwnerName"),
                               bounds={key: other[key] for key in ("X", "Y", "Width", "Height")})
                raise DesktopEnvironmentError(
                    "The macOS activation-click point is occluded by another window: " + json.dumps(blocker, sort_keys=True))

        def post(kind):
            event = Quartz.CGEventCreateMouseEvent(None, kind, point, Quartz.kCGMouseButtonLeft)
            if event is None:
                raise DesktopEnvironmentError("Cannot create macOS activation-click event")
            Quartz.CGEventSetFlags(event, 0)
            Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, 1)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            time.sleep(.03)

        try:
            try:
                post(Quartz.kCGEventLeftMouseDown)
            finally:
                post(Quartz.kCGEventLeftMouseUp)
        except Exception as error:
            raise DesktopEnvironmentError(f"macOS activation click failed: {error}") from error
        return dict(source="Quartz titlebar click", requested_pid=window["pid"], requested_window=window["id"],
                    point=list(point), window_rectangle=[left, top, left + width, top + height],
                    event_access="preflight_passed", events_posted=True)

    def focus(self, window):
        evidence = dict(status="not_run", requested_pid=window["pid"], requested_window=window["id"])
        self.last_focus = evidence
        try:
            if sys.platform.startswith("linux"):
                command(["xdotool", "windowactivate", "--sync", str(window["id"])])
                observed = command(["xdotool", "getactivewindow"]).stdout.strip()
                evidence.update(source="X11 active window", observed_window=observed)
                if observed != str(window["id"]):
                    raise DesktopEnvironmentError("X11 active window differs from the test window")
            elif sys.platform == "win32":
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                user32.SetForegroundWindow.argtypes = [wintypes.HWND]
                user32.GetForegroundWindow.restype = wintypes.HWND
                user32.SetForegroundWindow(window["id"])
                time.sleep(.2)
                observed = user32.GetForegroundWindow()
                evidence.update(source="Windows foreground window", observed_window=observed)
                if observed != window["id"]:
                    raise DesktopEnvironmentError("Cannot focus the test application's window")
            elif sys.platform == "darwin":
                command(["osascript", "-e", 'tell application "System Events" to set frontmost of '
                         f'(first process whose unix id is {int(window["pid"])}) to true'], timeout=5)
                # System Events' process list can disagree with the native
                # key-event recipient for standalone GTK. Retain it only as a
                # diagnostic; verify foreground through the documented API.
                # An Automation denial above is never retried via another path.
                try:
                    evidence["system_events_frontmost_pids"] = command(
                        ["osascript", "-e", 'tell application "System Events" to get unix id '
                         'of every process whose frontmost is true'], timeout=1, check=False).stdout.strip()
                except DesktopEnvironmentError as error:
                    evidence["system_events_frontmost_pids"] = f"unavailable: {error}"
                evidence["activation_clicks"] = []
                deadline = time.monotonic() + 3
                for attempt in range(1, 31):
                    observed = self.macos_frontmost_pid()
                    evidence.update(source="macOS NSWorkspace frontmost application", observed_pid=observed, attempts=attempt)
                    if observed == str(window["pid"]):
                        break
                    if time.monotonic() >= deadline or attempt == 30:
                        raise DesktopEnvironmentError(
                            f"macOS frontmost PID {observed!r} differs from test PID {window['pid']}")
                    if attempt == 2:
                        evidence["activation_clicks"].append(self.macos_activation_click(window))
                    time.sleep(.1)
            else:
                raise DesktopEnvironmentError(f"Unsupported input host: {sys.platform}")
        except DesktopEnvironmentError as error:
            evidence.update(status="environment_error", reason=str(error))
            raise
        time.sleep(.2)
        evidence["status"] = "passed"
        return evidence

    @staticmethod
    def macos_key(code, command_modifier=False):
        """Post physical transitions, not a key event with modifier flags only.

        Winit consumers can derive modifier state from the real Command key's
        flagsChanged event. All pressed keys get a release attempt in finally.
        TCC is checked without requesting access or falling back to another route.
        """
        import Quartz
        if not hasattr(Quartz, "CGPreflightPostEventAccess") or not Quartz.CGPreflightPostEventAccess():
            raise DesktopEnvironmentError("macOS keyboard event-posting permission unavailable; no TCC prompt attempted")
        mask = Quartz.kCGEventFlagMaskCommand if command_modifier else 0

        def post(keycode, down, flags, *, modifier=False):
            event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
            if event is None:
                raise DesktopEnvironmentError("Cannot create macOS keyboard event")
            if modifier:
                Quartz.CGEventSetType(event, Quartz.kCGEventFlagsChanged)
            Quartz.CGEventSetFlags(event, flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            time.sleep(.03)

        modifier_attempted = key_attempted = False
        try:
            try:
                if command_modifier:
                    modifier_attempted = True
                    post(55, True, mask, modifier=True)  # kVK_Command, physical left Command.
                key_attempted = True
                post(code, True, mask)
            finally:
                try:
                    if key_attempted:
                        post(code, False, mask)
                finally:
                    if modifier_attempted:
                        post(55, False, 0, modifier=True)
        except Exception as error:
            raise DesktopEnvironmentError(f"macOS keyboard event injection failed: {error}") from error

    def key(self, name, *, command_modifier=False):
        if sys.platform.startswith("linux"):
            key = ("ctrl+" if command_modifier else "") + name
            command(["xdotool", "key", "--clearmodifiers", key])
        elif sys.platform == "win32":
            keys = {"f": 0x46, "a": 0x41, "c": 0x43, "v": 0x56,
                    "BackSpace": 0x08, "Tab": 0x09}
            sequence = ([0x11] if command_modifier else []) + [keys[name]]
            for key in sequence:
                ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            for key in reversed(sequence):
                ctypes.windll.user32.keybd_event(key, 0, 0x0002, 0)
        elif sys.platform == "darwin":
            code = {"a": 0, "f": 3, "c": 8, "v": 9, "BackSpace": 51, "Tab": 48}[name]
            self.macos_key(code, command_modifier)
        else:
            raise DesktopEnvironmentError(f"Unsupported input host: {sys.platform}")
        time.sleep(.15)

    def park_pointer(self):
        if sys.platform.startswith("linux"):
            command(["xdotool", "mousemove", "1", "1"])
        elif sys.platform == "win32":
            ctypes.windll.user32.SetCursorPos(1, 1)
        else:
            import Quartz
            event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved,
                                                  (1, 1), Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def content_luminance(path):
    with Image.open(path) as image:
        if image.width < 100 or image.height < 100:
            raise RuntimeError("Appearance capture is too small")
        client = image.convert("L").crop((20, 60, image.width - 20, image.height - 20))
        return round(ImageStat.Stat(client).mean[0], 3)


def matches_theme(luma, theme):
    return luma < 110 if theme == "dark" else luma > 170


def acceptance_passed(result):
    """All required checks must have real evidence; absence is never a pass."""
    return all(result.get(key, {}).get("status") == "passed"
               for key in ("startup_theme", "live_theme", "clipboard"))


def live_theme_status(transitions):
    """A host failure is environment_error, never a framework failure."""
    statuses = [t["status"] for t in transitions]
    if len(statuses) == 2 and all(status == "passed" for status in statuses):
        return "passed"
    return "failed" if "failed" in statuses else "environment_error" if "environment_error" in statuses else "failed"


def acceptance_status(result):
    if acceptance_passed(result):
        return "passed"
    statuses = [result.get(key, {}).get("status") for key in ("startup_theme", "live_theme", "clipboard")]
    return "environment_error" if "environment_error" in statuses and "failed" not in statuses else "failed"


class DesktopChecks:
    def __init__(self, output, startup_theme="light"):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.initial = startup_theme
        self.theme = SystemTheme()
        self.clipboard = Clipboard()
        self.input = DesktopInput()
        self.result = dict(schema_version=1, profile="desktop-acceptance-v1", status="not_run",
                           startup_theme={"status": "not_run"}, live_theme={"status": "not_run"},
                           clipboard={"status": "not_run"}, cleanup={"status": "not_run"},
                           limitations=[
                               "Appearance is verified by OS preference plus client-luminance heuristics; inspect screenshots for occlusion and custom styling",
                               "Clipboard tests cover Unicode text via standard widget shortcuts, not images, files, rich text or X11 primary selection",
                               "This driver verifies Linux X11 only, not native Wayland",
                               "Synthetic clipboard content replaces existing content; run only in a disposable desktop session"])

    def save(self):
        (self.output / "desktop-integration.json").write_text(
            json.dumps(self.result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def prepare(self):
        try:
            if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland":
                raise DesktopEnvironmentError("Native Wayland input is not implemented; an XWayland window is not native Wayland coverage")
            if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
                raise DesktopEnvironmentError("An isolated X11 DISPLAY is required")
            self.theme.snapshot()
            self.result["system_theme_setup"] = dict(status="passed", requested=self.initial,
                                                      observed=self.theme.set(self.initial))
        except Exception as error:
            self.result.update(status="environment_error", reason=f"{type(error).__name__}: {error}")
            self.result["system_theme_setup"] = dict(status="failed", reason=str(error))
            raise
        finally:
            self.save()

    def stable_window(self, get_window, identity):
        window = get_window()
        if not window or (window.get("pid"), window["id"]) != identity:
            raise RuntimeError("Application window/PID changed during live desktop checks")
        return window

    def appearance(self, theme, label, get_window, identity, capture, *, timeout_seconds=8):
        path = self.output / f"desktop-{label}.png"
        started = time.monotonic()
        deadline = started + timeout_seconds
        attempts, luma, last_error = 0, None, None
        while True:
            attempts += 1
            try:
                window = self.stable_window(get_window, identity)
            except Exception as error:
                return dict(status="failed", expected=theme, same_window_and_pid=False,
                            attempts=attempts, reason=f"{type(error).__name__}: {error}",
                            timeout_seconds=timeout_seconds,
                            elapsed_seconds=round(time.monotonic() - started, 3))
            try:
                capture(window, path)
                luma = content_luminance(path)
                if matches_theme(luma, theme):
                    return dict(status="passed", expected=theme, mean_client_luma=luma,
                                screenshot=path.name, attempts=attempts, same_window_and_pid=True,
                                timeout_seconds=timeout_seconds,
                                elapsed_seconds=round(time.monotonic() - started, 3))
                last_error = f"Client luminance {luma} does not match {theme}"
            except Exception as error:
                last_error = f"{type(error).__name__}: {error}"
            observed = time.monotonic()
            if observed >= deadline:
                return dict(status="failed", expected=theme, mean_client_luma=luma,
                            screenshot=path.name if path.exists() else None,
                            attempts=attempts, same_window_and_pid=True, reason=last_error,
                            timeout_seconds=timeout_seconds,
                            elapsed_seconds=round(observed - started, 3))
            time.sleep(.2)

    def check_clipboard(self, get_window, identity, capture):
        nonce = uuid.uuid4().hex[:12]
        payload = f"desktop-{nonce} München — Привет ✓"
        sentinel = f"not-the-widget-{nonce}"
        result = dict(status="failed", expected_utf8=payload, sentinel_utf8=sentinel,
                      protocol="external Unicode seed → Ctrl/Cmd+V into filter → replace OS clipboard → Ctrl/Cmd+C → external read")
        self.result["clipboard"] = result
        window = self.stable_window(get_window, identity)
        try:
            result["focus"] = self.input.focus(window)
        finally:
            if "focus" not in result and hasattr(self.input, "last_focus"):
                result["focus"] = self.input.last_focus
        self.input.key("f", command_modifier=True)
        self.input.key("a", command_modifier=True)
        self.clipboard.write(payload)
        self.input.key("v", command_modifier=True)
        time.sleep(.3)
        capture(self.stable_window(get_window, identity), self.output / "desktop-clipboard-pasted.png")
        result["pasted_screenshot"] = "desktop-clipboard-pasted.png"
        # Crucial negative control: if copy is ignored, reading the seed would be
        # a false pass. It must now replace an independently written sentinel.
        self.clipboard.write(sentinel)
        result["sentinel_verified"] = self.clipboard.read() == sentinel
        if not result["sentinel_verified"]:
            raise DesktopEnvironmentError("Clipboard negative-control sentinel was not installed")
        self.input.key("a", command_modifier=True)
        self.input.key("c", command_modifier=True)
        deadline = time.monotonic() + 5
        while True:
            copied = self.clipboard.read()
            if copied == payload:
                result.update(status="passed", copied_utf8=copied)
                break
            if time.monotonic() >= deadline:
                result.update(copied_utf8=copied, reason="External clipboard did not receive the exact widget text")
                break
            time.sleep(.1)
        # Leave the ordinary fixture state reproducible and stop cursor blinking.
        self.input.key("a", command_modifier=True)
        self.input.key("BackSpace")
        self.input.key("Tab")
        self.input.park_pointer()
        capture(self.stable_window(get_window, identity), self.output / "desktop-ready-for-idle.png")
        result["restored_fixture_screenshot"] = "desktop-ready-for-idle.png"
        return result

    def run(self, get_window, capture):
        window = get_window()
        if not window:
            raise RuntimeError("No application window for desktop checks")
        identity = (window.get("pid"), window["id"])
        self.result["application_window"] = dict(pid=identity[0], id=identity[1])
        try:
            # A mapped window is not necessarily foreground on macOS. Establish
            # the same ordinary foreground workload before the first palette
            # capture, not just immediately before clipboard keyboard input.
            self.result["startup_focus"] = self.input.focus(window)
        except DesktopEnvironmentError as error:
            self.result["startup_focus"] = getattr(self.input, "last_focus", dict(status="environment_error", reason=str(error)))
            self.result.update(status="environment_error", reason=f"Initial foreground activation failed: {error}")
            # Diagnostic only: a failed focus gate must never become an
            # appearance/clipboard pass, but preserve the actual owned window.
            path = self.output / "desktop-startup-focus-failure.png"
            try:
                capture(self.stable_window(get_window, identity), path)
                self.result["startup_focus"]["failure_capture"] = dict(status="captured", screenshot=path.name)
            except Exception as capture_error:
                self.result["startup_focus"]["failure_capture"] = dict(
                    status="unavailable", reason=f"{type(capture_error).__name__}: {capture_error}")
            self.save()
            return self.result
        # A mapped native window can precede a webview's first rendered page by
        # several seconds on a cold runner. All candidates get the same bounded
        # startup budget; live palette changes retain their separate 8s deadline.
        # Blank captures, a wrong palette, and a replaced window/PID still fail.
        self.result["startup_theme"] = self.appearance(
            self.initial, "startup", get_window, identity, capture, timeout_seconds=30)
        self.save()
        transitions = []
        opposite = "dark" if self.initial == "light" else "light"
        previous = self.result["startup_theme"].get("mean_client_luma")
        for index, theme in enumerate((opposite, self.initial), 1):
            try:
                setting = self.theme.set(theme)
                transition = self.appearance(theme, f"live-{index}-{theme}", get_window, identity, capture)
                transition["system_setting"] = setting
                luma = transition.get("mean_client_luma")
                if luma is not None and previous is not None:
                    transition["luminance_delta"] = round(abs(luma - previous), 3)
                    if abs(luma - previous) <= 60:
                        transition.update(status="failed", reason="Client luminance did not change by more than 60/255")
                else:
                    transition.update(status="failed", reason="A transition capture has no luminance evidence")
                previous = luma
            except DesktopEnvironmentError as error:
                transition = dict(status="environment_error", expected=theme, reason=str(error))
            except Exception as error:
                transition = dict(status="failed", expected=theme, reason=f"{type(error).__name__}: {error}")
            transitions.append(transition)
            self.result["live_theme"] = dict(status=live_theme_status(transitions), transitions=transitions)
            self.save()
        try:
            self.check_clipboard(get_window, identity, capture)
        except DesktopEnvironmentError as error:
            self.result["clipboard"].update(status="environment_error", reason=str(error))
        except Exception as error:
            self.result["clipboard"].update(status="failed", reason=f"{type(error).__name__}: {error}")
        finally:
            try:
                self.clipboard.close()
                self.result["clipboard"]["probe_helpers_reaped_before_idle"] = True
            except Exception as error:
                self.result["clipboard"].update(status="environment_error", reason=f"Clipboard helper cleanup: {error}")
        self.result["status"] = acceptance_status(self.result)
        self.save()
        return self.result

    def close(self):
        errors = []
        for name, cleanup in (("clipboard_helpers", self.clipboard.close), ("system_theme", self.theme.restore)):
            try:
                cleanup()
            except Exception as error:
                errors.append(f"{name}: {type(error).__name__}: {error}")
        self.result["cleanup"] = dict(status="failed" if errors else "passed", errors=errors)
        if errors:
            self.result["status"] = "failed"
        self.save()
        return not errors
