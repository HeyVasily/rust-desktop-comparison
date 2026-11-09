"""Host-free regressions for external desktop acceptance and false-pass refusal."""
import ctypes
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

import desktop_probe as probe


class FakeClipboard:
    def __init__(self):
        self.value = ""
        self.events = []

    def write(self, text):
        self.events.append(("external-write", text))
        self.value = text

    def read(self):
        self.events.append(("external-read", self.value))
        return self.value

    def close(self):
        self.events.append(("close",))


class FakeInput:
    def __init__(self, clipboard, copy=True, paste=True):
        self.clipboard = clipboard
        self.widget = ""
        self.copy = copy
        self.paste = paste

    def focus(self, window):
        self.clipboard.events.append(("focus", window["id"]))

    def key(self, name, *, command_modifier=False):
        self.clipboard.events.append(("key", name, command_modifier))
        if name == "v" and self.paste:
            self.widget = self.clipboard.value
        if name == "c" and self.copy:
            self.clipboard.value = self.widget
        if name == "BackSpace":
            self.widget = ""

    def park_pointer(self):
        self.clipboard.events.append(("park-pointer",))


class DesktopProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.window = dict(id=123, pid=42, rectangle=[0, 0, 960, 640])

    def checks(self, copy=True, paste=True):
        checker = probe.DesktopChecks(self.output)
        checker.clipboard = FakeClipboard()
        checker.input = FakeInput(checker.clipboard, copy=copy, paste=paste)
        return checker

    def test_decode_exact_portal_variants_and_refuse_unknown_values(self):
        for text, expected in (("(<uint32 1>,)\n", 1), ("(<uint32 2>,)", 2), ("(<0>,)", 0)):
            self.assertEqual(probe.portal_color_scheme(text), expected)
        for text in ("error: expected uint32 1", "(<uint32 3>,)", "(<'dark'>,)", ""):
            with self.assertRaises(probe.DesktopEnvironmentError):
                probe.portal_color_scheme(text)

    def test_missing_host_command_is_an_environment_error(self):
        with patch.object(probe.subprocess, "run", side_effect=FileNotFoundError("missing tool")):
            with self.assertRaises(probe.DesktopEnvironmentError):
                probe.command(["missing-tool"])

    def test_fresh_windows_profile_without_personalize_key_can_be_snapshotted(self):
        registry = Mock(OpenKey=Mock(side_effect=FileNotFoundError("No Personalize key")))
        theme = probe.SystemTheme()
        with patch.object(probe.sys, "platform", "win32"), patch.dict("sys.modules", winreg=registry):
            theme.snapshot()
        self.assertEqual(theme.saved, {"AppsUseLightTheme": None, "SystemUsesLightTheme": None})
        registry.QueryValueEx.assert_not_called()

    def test_windows_snapshot_permission_denial_is_not_treated_as_missing_key(self):
        registry = Mock(OpenKey=Mock(side_effect=PermissionError("denied")))
        with patch.object(probe.sys, "platform", "win32"), patch.dict("sys.modules", winreg=registry):
            with self.assertRaises(PermissionError):
                probe.SystemTheme().snapshot()

    def test_windows_clipboard_owner_pumps_and_dispatches_pending_messages(self):
        from ctypes import wintypes
        clipboard = probe.Clipboard()
        clipboard.window_handle = 2**40 + 7
        user32 = Mock()
        user32.PeekMessageW.side_effect = [True, True, False]
        with patch.object(probe.time, "monotonic", return_value=0):
            clipboard.pump_windows_messages(user32)
        self.assertEqual(user32.PeekMessageW.call_count, 3)
        self.assertEqual(user32.TranslateMessage.call_count, 2)
        self.assertEqual(user32.DispatchMessageW.call_count, 2)
        self.assertEqual(user32.PeekMessageW.call_args.args[1:], (2**40 + 7, 0, 0, 1))
        self.assertEqual(user32.PeekMessageW.argtypes[1], wintypes.HWND)
        self.assertEqual(user32.DispatchMessageW.restype, ctypes.c_ssize_t)

    def test_windows_clipboard_pump_is_bounded_when_messages_keep_arriving(self):
        clipboard = probe.Clipboard()
        clipboard.window_handle = 42
        user32 = Mock()
        user32.PeekMessageW.return_value = True
        with patch.object(probe.time, "monotonic", return_value=0):
            clipboard.pump_windows_messages(user32)
        self.assertEqual(user32.DispatchMessageW.call_count, 64)

    def test_windows_clipboard_pumps_before_initial_open_and_every_retry(self):
        clipboard = probe.Clipboard()
        clipboard.window_handle = 2**40 + 7
        events = []
        user32, kernel32 = Mock(), Mock()
        attempts = iter((False, True))
        def open_clipboard(handle):
            events.append(("open", handle))
            return next(attempts)
        user32.OpenClipboard.side_effect = open_clipboard
        with patch.object(probe.ctypes, "windll", Mock(user32=user32, kernel32=kernel32), create=True), \
                patch.object(clipboard, "pump_windows_messages", side_effect=lambda api: events.append(("pump", api))), \
                patch.object(probe.time, "monotonic", return_value=0), patch.object(probe.time, "sleep"):
            self.assertEqual(clipboard.windows_api(), (user32, kernel32))
        self.assertEqual([event[0] for event in events], ["pump", "open", "pump", "open"])
        self.assertEqual(events[1][1], 2**40 + 7)

    def test_clipboard_changes_external_seed_before_copy_and_checks_unicode_exactly(self):
        checker = self.checks()
        with patch.object(probe.time, "sleep"):
            result = checker.check_clipboard(lambda: self.window, (42, 123), Mock())
        self.assertEqual(result["status"], "passed")
        self.assertIn("München — Привет ✓", result["copied_utf8"])
        self.assertEqual(result["expected_utf8"], result["copied_utf8"])
        writes = [event for event in checker.clipboard.events if event[0] == "external-write"]
        self.assertEqual(len(writes), 2)
        self.assertNotEqual(writes[0][1], writes[1][1])
        events = checker.clipboard.events
        sentinel_position = events.index(writes[1])
        copy_position = events.index(("key", "c", True))
        self.assertLess(sentinel_position, copy_position)
        self.assertEqual(checker.input.widget, "")
        self.assertIn(("key", "Tab", False), events)

    def test_ignored_copy_cannot_pass_by_reading_the_original_seed(self):
        checker = self.checks(copy=False)
        with patch.object(probe.time, "sleep"), patch.object(probe.time, "monotonic", side_effect=[0, 6]):
            result = checker.check_clipboard(lambda: self.window, (42, 123), Mock())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["copied_utf8"], result["sentinel_utf8"])

    def test_ignored_paste_cannot_pass_even_when_copy_works(self):
        checker = self.checks(paste=False)
        with patch.object(probe.time, "sleep"), patch.object(probe.time, "monotonic", side_effect=[0, 6]):
            result = checker.check_clipboard(lambda: self.window, (42, 123), Mock())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["copied_utf8"], "")

    def test_no_checks_or_skipped_checks_do_not_count_as_acceptance(self):
        self.assertFalse(probe.acceptance_passed({}))
        checks = {key: {"status": "passed"} for key in ("startup_theme", "live_theme", "clipboard")}
        self.assertTrue(probe.acceptance_passed(checks))
        for status in ("failed", "not_run", "environment_error"):
            checks["clipboard"]["status"] = status
            self.assertFalse(probe.acceptance_passed(checks))

    def test_same_pid_but_replaced_window_is_refused(self):
        checker = self.checks()
        with self.assertRaisesRegex(RuntimeError, "window/PID changed"):
            checker.stable_window(lambda: {**self.window, "id": 124}, (42, 123))

    def test_same_window_handle_but_replaced_pid_is_refused(self):
        checker = self.checks()
        with self.assertRaisesRegex(RuntimeError, "window/PID changed"):
            checker.stable_window(lambda: {**self.window, "pid": 43}, (42, 123))

    def test_live_check_cannot_claim_same_window_after_replacement(self):
        checker = self.checks()
        result = checker.appearance("dark", "changed", lambda: {**self.window, "id": 999}, (42, 123), Mock())
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["same_window_and_pid"])

    def test_titlebar_is_excluded_from_appearance_luminance(self):
        image = Image.new("RGB", (960, 668), "#202020")
        ImageDraw.Draw(image).rectangle((0, 0, 959, 59), fill="white")
        image.save(self.output / "dark.png")
        self.assertEqual(probe.content_luminance(self.output / "dark.png"), 32)
        self.assertTrue(probe.matches_theme(32, "dark"))
        self.assertFalse(probe.matches_theme(32, "light"))

    def test_wrong_initial_appearance_is_failed_not_assumed_light(self):
        checker = self.checks()
        def capture(window, path):
            Image.new("RGB", (960, 640), "#202020").save(path)
        with patch.object(probe.time, "monotonic", side_effect=[0, 9]):
            result = checker.appearance("light", "startup", lambda: self.window, (42, 123), capture)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["mean_client_luma"], 32)

    def test_live_light_dark_light_records_both_transitions_and_reaps_helpers(self):
        checker = self.checks()
        state = {"theme": "light"}
        def set_theme(theme):
            state["theme"] = theme
            return dict(source="fake-os", theme=theme)
        checker.theme = Mock(set=Mock(side_effect=set_theme))
        def capture(window, path):
            Image.new("RGB", (960, 640), "white" if state["theme"] == "light" else "#202020").save(path)
        with patch.object(probe.time, "sleep"):
            result = checker.run(lambda: self.window, capture)
        self.assertEqual(result["status"], "passed")
        self.assertEqual([call.args[0] for call in checker.theme.set.call_args_list], ["dark", "light"])
        self.assertEqual(len(result["live_theme"]["transitions"]), 2)
        self.assertTrue(result["clipboard"]["probe_helpers_reaped_before_idle"])
        self.assertEqual(checker.clipboard.events[-1], ("close",))

    def test_prepare_refuses_native_wayland_instead_of_claiming_xwayland_coverage(self):
        checker = self.checks()
        with patch.object(probe.sys, "platform", "linux"), patch.dict(os.environ, XDG_SESSION_TYPE="wayland", DISPLAY=":1"):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "Native Wayland"):
                checker.prepare()
        self.assertEqual(checker.result["status"], "environment_error")
        self.assertEqual(checker.result["startup_theme"]["status"], "not_run")

    def test_cleanup_failure_invalidates_pass_and_is_preserved(self):
        checker = self.checks()
        checker.result["status"] = "passed"
        checker.theme = Mock(restore=Mock(side_effect=RuntimeError("restore failed")))
        self.assertFalse(checker.close())
        self.assertEqual(checker.result["status"], "failed")
        self.assertIn("restore failed", checker.result["cleanup"]["errors"][0])


if __name__ == "__main__":
    unittest.main()
