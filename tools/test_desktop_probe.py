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
        return dict(status="passed", source="synthetic-test", observed_pid=window["pid"])

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
    def test_host_error_in_live_theme_is_not_a_framework_failure(self):
        passed, host = dict(status="passed"), dict(status="environment_error")
        self.assertEqual(probe.live_theme_status([passed, passed]), "passed")
        self.assertEqual(probe.live_theme_status([passed, host]), "environment_error")
        self.assertEqual(probe.live_theme_status([dict(status="failed"), host]), "failed")
        self.assertEqual(probe.live_theme_status([passed]), "failed")
        result = dict(startup_theme=passed, live_theme=dict(status="environment_error"), clipboard=passed)
        self.assertEqual(probe.acceptance_status(result), "environment_error")
        result["clipboard"] = dict(status="failed")
        self.assertEqual(probe.acceptance_status(result), "failed")
        self.assertEqual(probe.acceptance_status({}), "failed")

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

    def test_linux_theme_snapshots_sets_and_restores_both_shared_preferences(self):
        theme = probe.SystemTheme()
        with patch.object(probe.sys, "platform", "linux"), \
                patch.object(probe, "command", side_effect=[Mock(stdout="'default'\n"), Mock(stdout="'Original theme'\n")]):
            theme.snapshot()
        self.assertEqual(theme.saved, {"color-scheme": "'default'", "gtk-theme": "'Original theme'"})
        with patch.object(probe.sys, "platform", "linux"), patch.object(probe, "command") as command, \
                patch.object(theme, "read", return_value=dict(theme="dark", gtk_theme="Adwaita-dark")):
            theme.set("dark")
        commands = [call.args[0] for call in command.call_args_list]
        self.assertIn(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Adwaita-dark"], commands)
        self.assertIn(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark"], commands)
        with patch.object(probe.sys, "platform", "linux"), patch.object(probe, "command") as command:
            theme.restore()
        self.assertEqual([call.args[0][-2:] for call in command.call_args_list],
                         [["color-scheme", "'default'"], ["gtk-theme", "'Original theme'"]])

    def test_linux_theme_reads_effective_gtk_xsettings_not_just_the_stored_key(self):
        theme = probe.SystemTheme()
        with patch.object(probe.sys, "platform", "linux"), \
                patch.object(probe, "command", side_effect=[
                    Mock(returncode=0, stdout="(<uint32 1>,)"),
                    Mock(stdout='    gtk-theme-name: "Adwaita-dark"\n')]) as command:
            setting = theme.read()
        self.assertEqual(setting["theme"], "dark")
        self.assertEqual(setting["gtk_theme"], "Adwaita-dark")
        self.assertEqual(setting["session_profile"], "gnome-adwaita-dual-preference-v1")
        self.assertEqual(command.call_args.args[0], ["gtk-query-settings", "gtk-theme-name"])

    def test_linux_theme_refuses_disagreement_between_portal_and_effective_gtk_theme(self):
        with patch.object(probe.sys, "platform", "linux"), \
                patch.object(probe, "command", side_effect=[
                    Mock(returncode=0, stdout="(<uint32 1>,)"), Mock(stdout='gtk-theme-name: "Adwaita"\n')]):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "inconsistent"):
                probe.SystemTheme().read()

    def test_linux_theme_restore_attempts_both_keys_even_if_one_fails(self):
        theme = probe.SystemTheme()
        theme.saved = {"color-scheme": "'default'", "gtk-theme": "'Adwaita'"}
        with patch.object(probe.sys, "platform", "linux"), \
                patch.object(probe, "command", side_effect=[probe.DesktopEnvironmentError("failed first key"), Mock()]) as command:
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "restoration failed"):
                theme.restore()
        self.assertEqual(command.call_count, 2)

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

    def test_macos_focus_waits_for_actual_frontmost_pid_and_records_evidence(self):
        driver = probe.DesktopInput()
        with patch.object(probe.sys, "platform", "darwin"), \
                patch.object(probe, "command", return_value=Mock(stdout="7\n")) as command, \
                patch.object(driver, "macos_frontmost_pid", side_effect=["7", "42"]) as frontmost, \
                patch.object(driver, "macos_activation_click") as click, \
                patch.object(probe.time, "monotonic", return_value=0), patch.object(probe.time, "sleep"):
            evidence = driver.focus(self.window)
        self.assertEqual(command.call_count, 2)
        self.assertEqual(frontmost.call_count, 2)
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["source"], "macOS NSWorkspace frontmost application")
        self.assertEqual(evidence["observed_pid"], "42")
        self.assertEqual(evidence["system_events_frontmost_pids"], "7")
        self.assertEqual(evidence["attempts"], 2)
        self.assertEqual(command.call_args.kwargs["timeout"], 1)
        click.assert_not_called()
        self.assertEqual(evidence["activation_clicks"], [])

    def test_macos_focus_failure_is_bounded_and_not_a_clipboard_capability_failure(self):
        driver = probe.DesktopInput()
        with patch.object(probe.sys, "platform", "darwin"), \
                patch.object(probe, "command", return_value=Mock(stdout="7\n")), \
                patch.object(driver, "macos_frontmost_pid", return_value="7"), \
                patch.object(driver, "macos_activation_click") as click, \
                patch.object(probe.time, "monotonic", side_effect=[0, 4]), patch.object(probe.time, "sleep"):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "frontmost PID"):
                driver.focus(self.window)
        self.assertEqual(driver.last_focus["status"], "environment_error")
        self.assertEqual(driver.last_focus["observed_pid"], "7")
        click.assert_not_called()

    def test_macos_focus_permission_error_is_not_retried_or_bypassed(self):
        driver = probe.DesktopInput()
        with patch.object(probe.sys, "platform", "darwin"), \
                patch.object(probe, "command", side_effect=probe.DesktopEnvironmentError("Automation permission denied")) as command, \
                patch.object(driver, "macos_frontmost_pid") as frontmost, \
                patch.object(driver, "macos_activation_click") as click:
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "permission denied"):
                driver.focus(self.window)
        self.assertEqual(command.call_count, 1)
        frontmost.assert_not_called()
        click.assert_not_called()
        self.assertEqual(driver.last_focus["status"], "environment_error")

    def test_macos_focus_observations_are_bounded_even_when_click_posts_successfully(self):
        driver = probe.DesktopInput()
        with patch.object(probe.sys, "platform", "darwin"), \
                patch.object(probe, "command", return_value=Mock(stdout="7\n")), \
                patch.object(driver, "macos_frontmost_pid", return_value="7"), \
                patch.object(driver, "macos_activation_click", return_value={"events_posted": True}) as click, \
                patch.object(probe.time, "monotonic", return_value=0), patch.object(probe.time, "sleep"):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "frontmost PID"):
                driver.focus(self.window)
        click.assert_called_once_with(self.window)
        self.assertEqual(driver.last_focus["attempts"], 30)
        self.assertEqual(driver.last_focus["status"], "environment_error")

    def test_macos_focus_can_activate_by_one_real_click_but_still_checks_actual_pid(self):
        driver = probe.DesktopInput()
        with patch.object(probe.sys, "platform", "darwin"), \
                patch.object(probe, "command", return_value=Mock(stdout="7\n")), \
                patch.object(driver, "macos_frontmost_pid", side_effect=["7", "7", "42"]), \
                patch.object(driver, "macos_activation_click", return_value={"events_posted": True}) as click, \
                patch.object(probe.time, "monotonic", return_value=0), patch.object(probe.time, "sleep"):
            evidence = driver.focus(self.window)
        click.assert_called_once_with(self.window)
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["observed_pid"], "42")
        self.assertEqual(evidence["activation_clicks"], [{"events_posted": True}])

    def test_macos_frontmost_uses_a_read_only_isolated_jxa_helper(self):
        with patch.object(probe, "command", return_value=Mock(stdout="42\n")) as command:
            self.assertEqual(probe.DesktopInput.macos_frontmost_pid(), "42")
        args = command.call_args.args[0]
        self.assertEqual(args[:4], ["osascript", "-l", "JavaScript", "-e"])
        self.assertIn("NSWorkspace.sharedWorkspace.frontmostApplication", args[4])
        self.assertIn("front.isNil()", args[4])
        self.assertNotIn("activate", args[4])
        self.assertNotIn("NSApplication", args[4])
        self.assertEqual(command.call_args.kwargs["timeout"], 2)

    def test_macos_frontmost_rejects_missing_or_invalid_pid_without_fallback(self):
        for value in ("0", "null", "", "42.0", "true", "42, 7"):
            with self.subTest(value=value), patch.object(probe, "command", return_value=Mock(stdout=value)):
                with self.assertRaisesRegex(probe.DesktopEnvironmentError, "Invalid NSWorkspace"):
                    probe.DesktopInput.macos_frontmost_pid()

    def test_macos_frontmost_observer_failure_never_trusts_system_events_instead(self):
        driver = probe.DesktopInput()
        with patch.object(probe.sys, "platform", "darwin"), \
                patch.object(probe, "command", return_value=Mock(stdout="42\n")), \
                patch.object(driver, "macos_frontmost_pid", side_effect=probe.DesktopEnvironmentError("observer unavailable")), \
                patch.object(driver, "macos_activation_click") as click:
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "observer unavailable"):
                driver.focus(self.window)
        click.assert_not_called()
        self.assertEqual(driver.last_focus["status"], "environment_error")

    def mouse_quartz(self):
        target = {"kCGWindowNumber": 123, "kCGWindowOwnerPID": 42, "kCGWindowLayer": 0,
                  "kCGWindowBounds": {"X": 50, "Y": 100, "Width": 960, "Height": 640}}
        api = Mock(kCGWindowListOptionOnScreenOnly=1, kCGWindowListExcludeDesktopElements=16,
                   kCGNullWindowID=0, kCGMouseButtonLeft=0, kCGEventLeftMouseDown=1,
                   kCGEventLeftMouseUp=2, kCGMouseEventClickState=1, kCGHIDEventTap=0)
        api.CGPreflightPostEventAccess.return_value = True
        api.CGWindowListCopyWindowInfo.return_value = [target]
        events = []
        def create(source, kind, point, button):
            event = dict(kind=kind, point=point, button=button)
            events.append(event)
            return event
        api.CGEventCreateMouseEvent.side_effect = create
        return api, events, target

    def test_macos_activation_click_refreshes_owned_window_bounds_and_releases_button(self):
        api, events, _ = self.mouse_quartz()
        with patch.dict("sys.modules", Quartz=api), patch.object(probe.time, "sleep"):
            evidence = probe.DesktopInput.macos_activation_click(self.window)
        self.assertEqual([(event["kind"], event["point"]) for event in events], [(1, (530, 112)), (2, (530, 112))])
        self.assertEqual(evidence["window_rectangle"], [50, 100, 1010, 740])
        self.assertEqual(evidence["event_access"], "preflight_passed")
        self.assertTrue(evidence["events_posted"])
        self.assertNotIn("status", evidence)

    def test_macos_activation_click_denied_permission_never_posts_or_requests_access(self):
        api, events, _ = self.mouse_quartz()
        api.CGPreflightPostEventAccess.return_value = False
        with patch.dict("sys.modules", Quartz=api):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "permission unavailable"):
                probe.DesktopInput.macos_activation_click(self.window)
        self.assertEqual(events, [])
        api.CGRequestPostEventAccess.assert_not_called()

    def test_macos_activation_click_refuses_changed_ownership_or_missing_window(self):
        for change in ({"kCGWindowOwnerPID": 99}, {"kCGWindowNumber": 999}, {"kCGWindowLayer": 1}):
            with self.subTest(change=change):
                api, events, target = self.mouse_quartz()
                target.update(change)
                with patch.dict("sys.modules", Quartz=api):
                    with self.assertRaisesRegex(probe.DesktopEnvironmentError, "exact owned"):
                        probe.DesktopInput.macos_activation_click(self.window)
                self.assertEqual(events, [])

    def test_macos_activation_click_refuses_an_occluding_window(self):
        api, events, target = self.mouse_quartz()
        api.CGWindowListCopyWindowInfo.return_value.insert(0, {**target, "kCGWindowNumber": 999,
                                                            "kCGWindowOwnerName": "Synthetic blocker"})
        with patch.dict("sys.modules", Quartz=api):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "occluded") as raised:
                probe.DesktopInput.macos_activation_click(self.window)
        self.assertIn('"window_id": 999', str(raised.exception))
        self.assertIn('"pid": 42', str(raised.exception))
        self.assertIn('"owner_name": "Synthetic blocker"', str(raised.exception))
        self.assertIn('"Width": 960', str(raised.exception))
        self.assertEqual(events, [])

    def test_macos_activation_click_releases_button_after_posting_exception(self):
        api, events, _ = self.mouse_quartz()
        api.CGEventPost.side_effect = [RuntimeError("synthetic posting failure"), None]
        with patch.dict("sys.modules", Quartz=api), patch.object(probe.time, "sleep"):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "posting failure"):
                probe.DesktopInput.macos_activation_click(self.window)
        self.assertEqual([event["kind"] for event in events], [1, 2])

    def quartz(self, fail_key_down=False):
        events = []
        api = Mock(kCGEventFlagMaskCommand=1 << 20, kCGEventFlagsChanged=12, kCGHIDEventTap=0)
        api.CGPreflightPostEventAccess.return_value = True
        def create(source, code, down):
            event = dict(code=code, down=down)
            events.append(event)
            return event
        api.CGEventCreateKeyboardEvent.side_effect = create
        api.CGEventSetType.side_effect = lambda event, kind: event.update(type=kind)
        api.CGEventSetFlags.side_effect = lambda event, flags: event.update(flags=flags)
        def post(tap, event):
            if fail_key_down and event["code"] == 3 and event["down"]:
                raise RuntimeError("synthetic posting failure")
        api.CGEventPost.side_effect = post
        return api, events

    def test_macos_shortcut_posts_real_modifier_and_key_transitions_in_order(self):
        api, events = self.quartz()
        with patch.dict("sys.modules", Quartz=api), patch.object(probe.time, "sleep"):
            probe.DesktopInput.macos_key(3, command_modifier=True)
        self.assertEqual([(event["code"], event["down"]) for event in events],
                         [(55, True), (3, True), (3, False), (55, False)])
        self.assertEqual([event["flags"] for event in events], [1 << 20, 1 << 20, 1 << 20, 0])
        self.assertEqual([event.get("type") for event in events], [12, None, None, 12])

    def test_macos_shortcut_releases_key_and_command_even_after_posting_error(self):
        api, events = self.quartz(fail_key_down=True)
        with patch.dict("sys.modules", Quartz=api), patch.object(probe.time, "sleep"):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "posting failure"):
                probe.DesktopInput.macos_key(3, command_modifier=True)
        self.assertEqual([(event["code"], event["down"]) for event in events],
                         [(55, True), (3, True), (3, False), (55, False)])
        self.assertEqual(events[-1]["flags"], 0)

    def test_macos_posting_permission_denial_does_not_post_or_request_access(self):
        api, events = self.quartz()
        api.CGPreflightPostEventAccess.return_value = False
        with patch.dict("sys.modules", Quartz=api):
            with self.assertRaisesRegex(probe.DesktopEnvironmentError, "permission unavailable"):
                probe.DesktopInput.macos_key(3, command_modifier=True)
        self.assertEqual(events, [])
        api.CGRequestPostEventAccess.assert_not_called()

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

    def test_cold_startup_waits_for_real_rendering_beyond_live_transition_budget(self):
        checker = self.checks()
        clock = [0]
        captures = []
        def capture(window, path):
            captures.append(path)
            if len(captures) == 1:
                clock[0] = 9
                raise RuntimeError("Capture is near-uniform; desktop rendering not established")
            clock[0] = 10
            Image.new("RGB", (960, 640), "white").save(path)
        with patch.object(probe.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(probe.time, "sleep"):
            result = checker.appearance(
                "light", "startup", lambda: self.window, (42, 123), capture, timeout_seconds=30)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["timeout_seconds"], 30)
        self.assertEqual(result["elapsed_seconds"], 10)

    def test_startup_rendering_wait_is_bounded_and_does_not_accept_blank_content(self):
        checker = self.checks()
        capture = Mock(side_effect=RuntimeError("Capture is near-uniform"))
        with patch.object(probe.time, "monotonic", side_effect=[0, 31]):
            result = checker.appearance(
                "light", "startup", lambda: self.window, (42, 123), capture, timeout_seconds=30)
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["mean_client_luma"])
        self.assertEqual(result["timeout_seconds"], 30)
        self.assertEqual(result["elapsed_seconds"], 31)

    def test_live_transition_retains_short_deadline_despite_longer_startup_budget(self):
        checker = self.checks()
        capture = Mock(side_effect=RuntimeError("Capture is near-uniform"))
        with patch.object(probe.time, "monotonic", side_effect=[0, 9]):
            result = checker.appearance("dark", "live-1-dark", lambda: self.window, (42, 123), capture)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["timeout_seconds"], 8)
        self.assertEqual(result["elapsed_seconds"], 9)

    def test_live_light_dark_light_records_both_transitions_and_reaps_helpers(self):
        checker = self.checks()
        state = {"theme": "light"}
        def set_theme(theme):
            state["theme"] = theme
            return dict(source="fake-os", theme=theme)
        checker.theme = Mock(set=Mock(side_effect=set_theme))
        def capture(window, path):
            self.assertEqual(checker.clipboard.events[0], ("focus", self.window["id"]))
            Image.new("RGB", (960, 640), "white" if state["theme"] == "light" else "#202020").save(path)
        with patch.object(probe.time, "sleep"):
            result = checker.run(lambda: self.window, capture)
        self.assertEqual(result["status"], "passed")
        self.assertEqual([call.args[0] for call in checker.theme.set.call_args_list], ["dark", "light"])
        self.assertEqual(len(result["live_theme"]["transitions"]), 2)
        self.assertEqual(result["startup_theme"]["timeout_seconds"], 30)
        self.assertEqual([transition["timeout_seconds"] for transition in result["live_theme"]["transitions"]], [8, 8])
        self.assertTrue(result["clipboard"]["probe_helpers_reaped_before_idle"])
        self.assertEqual(result["startup_focus"]["status"], "passed")
        self.assertEqual(result["clipboard"]["focus"]["status"], "passed")
        self.assertEqual(checker.clipboard.events[-1], ("close",))

    def test_startup_focus_failure_preserves_diagnostic_but_refuses_acceptance(self):
        checker = self.checks()
        checker.input.focus = Mock(side_effect=probe.DesktopEnvironmentError("Wrong frontmost PID"))
        capture = Mock()
        result = checker.run(lambda: self.window, capture)
        self.assertEqual(result["status"], "environment_error")
        self.assertEqual(result["startup_theme"]["status"], "not_run")
        self.assertEqual(result["clipboard"]["status"], "not_run")
        capture.assert_called_once_with(self.window, self.output / "desktop-startup-focus-failure.png")
        self.assertEqual(result["startup_focus"]["failure_capture"]["status"], "captured")

    def test_startup_focus_failure_preserves_original_failure_if_capture_is_unavailable(self):
        checker = self.checks()
        checker.input.focus = Mock(side_effect=probe.DesktopEnvironmentError("Wrong frontmost PID"))
        result = checker.run(lambda: self.window, Mock(side_effect=RuntimeError("capture unavailable")))
        self.assertEqual(result["status"], "environment_error")
        self.assertIn("Wrong frontmost PID", result["reason"])
        self.assertEqual(result["startup_theme"]["status"], "not_run")
        self.assertEqual(result["clipboard"]["status"], "not_run")
        self.assertEqual(result["startup_focus"]["failure_capture"]["status"], "unavailable")

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
