"""Test readiness and browser lifecycle without starting a browser or server."""
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import site_visual_smoke as smoke


class SiteVisualSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)

    def html(self, tables=0, cards=5):
        return '<article class="card fw"></article>' * cards + '<table class="data desktop-table"></table>' * tables

    def test_absent_dataset_is_an_explicit_skip_not_an_invented_table(self):
        result = smoke.inspect_dom(self.html(), False)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["desktop_tables"], 0)
        self.assertIn("skipped", result["desktop_table_assertion"])

    def test_present_dataset_requires_all_three_os_tables(self):
        self.assertEqual(smoke.inspect_dom(self.html(3), True)["status"], "passed")
        self.assertEqual(smoke.inspect_dom(self.html(2), True)["status"], "failed")

    def test_historical_loader_failure_is_not_a_pass(self):
        self.assertEqual(smoke.inspect_dom(self.html(cards=0), False)["status"], "failed")
        self.assertEqual(smoke.inspect_dom(self.html() + '<p class="error">Failed</p>', False)["status"], "failed")

    def test_flags_keep_the_browser_sandbox_enabled(self):
        self.assertIn("--headless", smoke.CHROME_FLAGS)
        self.assertFalse(any("sandbox" in flag for flag in smoke.CHROME_FLAGS))

    def run_browser(self, invocations):
        smoke.run_chrome("/usr/bin/google-chrome", "/tmp/test-profile", ["--dump-dom", "http://127.0.0.1:1234"],
                         self.output, "test", dbus_session="/usr/bin/dbus-run-session", invocations=invocations)

    def test_browser_uses_its_own_bus_and_bounded_sandboxed_invocation(self):
        process = Mock(pid=123, wait=Mock(return_value=0))
        invocations = []
        with patch.object(smoke.subprocess, "Popen", return_value=process) as start, \
                patch.object(smoke.os, "killpg") as kill, patch.object(smoke.time, "monotonic", side_effect=[10, 12]):
            self.run_browser(invocations)
        command = start.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/dbus-run-session", "--", "/usr/bin/google-chrome"])
        self.assertFalse(any("sandbox" in argument for argument in command))
        self.assertTrue(start.call_args.kwargs["start_new_session"])
        self.assertEqual(process.wait.call_args_list[0].kwargs["timeout"], 45)
        kill.assert_called_once_with(123, signal.SIGTERM)
        self.assertEqual(invocations[0]["status"], "passed")
        self.assertEqual(invocations[0]["elapsed_seconds"], 2)

    def test_timeout_remains_failure_is_recorded_and_cleans_only_owned_group(self):
        process = Mock(pid=123, wait=Mock(side_effect=[subprocess.TimeoutExpired("chrome", 45), 0]))
        invocations = []
        with patch.object(smoke.subprocess, "Popen", return_value=process) as start, \
                patch.object(smoke.os, "killpg") as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.run_browser(invocations)
        start.assert_called_once()  # No unrecorded retry or sandbox workaround.
        kill.assert_called_once_with(123, signal.SIGTERM)
        self.assertEqual(invocations[0]["status"], "failed")
        self.assertTrue(invocations[0]["timed_out"])

    def test_unresponsive_browser_group_is_killed_after_bounded_cleanup(self):
        process = Mock(pid=123, wait=Mock(side_effect=[subprocess.TimeoutExpired("chrome", 45),
                                                      subprocess.TimeoutExpired("chrome", 3), 0]))
        with patch.object(smoke.subprocess, "Popen", return_value=process), patch.object(smoke.os, "killpg") as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.run_browser([])
        self.assertEqual([call.args for call in kill.call_args_list], [(123, signal.SIGTERM), (123, signal.SIGKILL)])

    def test_nonzero_browser_exit_cannot_count_as_readiness_success(self):
        invocations = []
        process = Mock(pid=123, wait=Mock(return_value=2))
        with patch.object(smoke.subprocess, "Popen", return_value=process), patch.object(smoke.os, "killpg"):
            with self.assertRaisesRegex(RuntimeError, "exited with status 2"):
                self.run_browser(invocations)
        self.assertEqual(invocations[0]["status"], "failed")
        self.assertEqual(invocations[0]["returncode"], 2)

    def test_browser_launch_permission_error_is_not_retried_or_bypassed(self):
        invocations = []
        with patch.object(smoke.subprocess, "Popen", side_effect=PermissionError("denied")) as start, \
                patch.object(smoke.os, "killpg") as kill:
            with self.assertRaises(PermissionError):
                self.run_browser(invocations)
        start.assert_called_once()
        kill.assert_not_called()
        self.assertEqual(invocations[0]["status"], "failed")
        self.assertIn("denied", invocations[0]["reason"])

    def test_missing_session_tool_fails_before_launching_browser(self):
        with patch("sys.argv", ["site_visual_smoke.py", "--output", str(self.output)]), \
                patch.object(smoke.shutil, "which", side_effect=lambda name: "/usr/bin/google-chrome" if name == "google-chrome" else None), \
                patch.object(smoke.subprocess, "Popen") as start, patch("builtins.print"):
            self.assertEqual(smoke.main(), 1)
        start.assert_not_called()
        report = json.loads((self.output / "readiness.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertIn("dbus-run-session is missing", report["reason"])


if __name__ == "__main__":
    unittest.main()
