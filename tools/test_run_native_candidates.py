"""Host-free candidate ordering and strict publication-gate regressions."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import run_native_candidates as runner


class CandidateSelectionTests(unittest.TestCase):
    def setUp(self):
        self.target = Path("target-fixture")

    def test_selection_must_be_nonempty_unique_known_and_canonical(self):
        for selected in ([], ["unknown"], ["egui", "egui"], ["qt", "egui"], ["egui_reduced"]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                runner.selected_candidates(selected, self.target)

    def test_subset_keeps_canonical_order_and_unix_paths(self):
        selected = runner.selected_candidates(["gtk", "qt", "tauri"], self.target)
        self.assertEqual([item[0] for item in selected], ["gtk", "qt", "tauri"])
        self.assertEqual(selected[0][2], self.target / "release/veranda-gtk-comparison")
        self.assertEqual(selected[1][2], self.target / "qt/veranda-qt-comparison")
        self.assertEqual(selected[2][2], self.target / "release/veranda-tauri-comparison")

    def test_windows_keeps_gtk_gnu_runtime_and_qt_release_paths(self):
        selected = runner.selected_candidates(list(runner.NAMES), self.target, windows=True)
        paths = {name: path for name, _, path in selected}
        self.assertEqual(paths["gtk"], Path("target/msys2/release/veranda-gtk-comparison.exe"))
        self.assertEqual(paths["qt"], self.target / "qt/Release/veranda-qt-comparison.exe")
        self.assertEqual(paths["egui"], self.target / "release/veranda-egui-comparison.exe")

    def test_control_is_adjacent_and_alternates_order_without_replacing_primary(self):
        for repetition, expected in ((1, ["egui_reduced", "egui", "gtk"]),
                                     (2, ["egui", "egui_reduced", "gtk"]),
                                     (3, ["egui_reduced", "egui", "gtk"])):
            with self.subTest(repetition=repetition):
                selected = runner.selected_candidates(["egui", "gtk"], self.target,
                                                      reduced=True, repetition=repetition)
                self.assertEqual([item[0] for item in selected], expected)
                control = next(item for item in selected if item[0] == "egui_reduced")
                self.assertEqual(control[1], "Veranda egui comparison")
                self.assertEqual(control[2], self.target / "release/veranda-egui-reduced-comparison")

    def test_control_is_not_inserted_when_egui_is_unselected_or_disabled(self):
        self.assertEqual([item[0] for item in runner.selected_candidates(["gtk"], self.target, reduced=True)], ["gtk"])
        self.assertEqual([item[0] for item in runner.selected_candidates(["egui"], self.target, reduced=False)], ["egui"])


class VerificationGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.candidates = runner.selected_candidates(["egui"], Path("target-fixture"), reduced=True)
        self.write("failed-candidates.json", [])
        self.write("selected-candidates.json", [name for name, _, _ in self.candidates])
        for name, _, _ in self.candidates:
            outcome = self.valid_outcome(name)
            self.write(f"{name}/outcome.json", outcome)
            if name == "egui_reduced":
                self.write(f"{name}/control-system-theme.json", outcome["control_system_theme"])

    def write(self, relative, value):
        target = self.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def valid_outcome(self, name, comparison=True):
        outcome = dict(status="comparison_passed" if comparison else "diagnostic_passed",
                       cleanup_status="clean", phases={"comparison": {"summary": {"sample_intervals": 120}}})
        if name == "egui_reduced":
            outcome["measurement_profile"] = "diagnostic-reduced"
            outcome["control_system_theme"] = dict(schema_version=1, profile="control-system-theme-v1",
                status="passed", requested="light", observed={"theme": "light"},
                observed_after={"theme": "light"}, cleanup={"status": "passed"})
        else:
            outcome["measurement_profile"] = "desktop-integrated"
            outcome["desktop_integration"] = dict(status="passed", cleanup={"status": "passed"},
                **{key: {"status": "passed"} for key in ("startup_theme", "live_theme", "clipboard")})
        return outcome

    def test_valid_primary_and_separate_control_pass(self):
        runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_smoke_requires_acceptance_but_not_comparison_samples(self):
        for name, _, _ in self.candidates:
            outcome = self.valid_outcome(name, comparison=False)
            outcome["phases"] = {}
            self.write(f"{name}/outcome.json", outcome)
        runner.verify(self.output, self.candidates, comparison=False, desktop_checks=True)

    def test_no_aggregate_pass_can_hide_missing_failed_or_unrun_subcheck(self):
        for check in ("startup_theme", "live_theme", "clipboard"):
            for status in (None, "failed", "not_run", "environment_error"):
                with self.subTest(check=check, status=status):
                    outcome = self.valid_outcome("egui")
                    if status is None:
                        del outcome["desktop_integration"][check]
                    else:
                        outcome["desktop_integration"][check]["status"] = status
                    self.write("egui/outcome.json", outcome)
                    with self.assertRaises(AssertionError):
                        runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_primary_cannot_claim_legacy_profile_or_absent_desktop_result(self):
        for variation in ("legacy", "missing", "failed"):
            with self.subTest(variation=variation):
                outcome = self.valid_outcome("egui")
                if variation == "legacy":
                    outcome["measurement_profile"] = "legacy-ui-only"
                elif variation == "missing":
                    del outcome["desktop_integration"]
                else:
                    outcome["desktop_integration"]["status"] = "failed"
                self.write("egui/outcome.json", outcome)
                with self.assertRaises(AssertionError):
                    runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_control_must_have_explicit_diagnostic_profile(self):
        outcome = self.valid_outcome("egui_reduced")
        outcome["measurement_profile"] = "desktop-integrated"
        self.write("egui_reduced/outcome.json", outcome)
        with self.assertRaises(AssertionError):
            runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_control_requires_matching_verified_light_preference_before_and_after(self):
        for key, value in (("status", "not_run"), ("requested", "dark"),
                           ("observed", {"theme": "dark"}), ("observed_after", {}),
                           ("cleanup", {"status": "failed"})):
            with self.subTest(key=key):
                outcome = self.valid_outcome("egui_reduced")
                outcome["control_system_theme"][key] = value
                self.write("egui_reduced/outcome.json", outcome)
                with self.assertRaises(AssertionError):
                    runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_control_sidecar_must_match_embedded_evidence(self):
        self.write("egui_reduced/control-system-theme.json", {"status": "passed"})
        with self.assertRaises(AssertionError):
            runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_control_without_theme_evidence_is_not_a_valid_pair(self):
        outcome = self.valid_outcome("egui_reduced")
        del outcome["control_system_theme"]
        self.write("egui_reduced/outcome.json", outcome)
        with self.assertRaises(AssertionError):
            runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_dirty_or_unknown_cleanup_refuses_primary_publication(self):
        for field, value in (("cleanup_status", "unknown"), ("cleanup_status", "not_needed"),
                             ("desktop_cleanup", "not_run"), ("desktop_cleanup", "failed")):
            with self.subTest(field=field, value=value):
                outcome = self.valid_outcome("egui")
                if field == "desktop_cleanup":
                    outcome["desktop_integration"]["cleanup"]["status"] = value
                else:
                    outcome[field] = value
                self.write("egui/outcome.json", outcome)
                with self.assertRaises(AssertionError):
                    runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_incomplete_comparison_interval_count_refuses_publication(self):
        for intervals in (0, 10, 119, 121):
            with self.subTest(intervals=intervals):
                outcome = self.valid_outcome("egui")
                outcome["phases"]["comparison"]["summary"]["sample_intervals"] = intervals
                self.write("egui/outcome.json", outcome)
                with self.assertRaises(AssertionError):
                    runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_failed_candidate_list_cannot_be_ignored(self):
        self.write("failed-candidates.json", ["egui"])
        with self.assertRaises(AssertionError):
            runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_stale_extra_outcome_is_refused(self):
        self.write("unexpected/outcome.json", self.valid_outcome("egui"))
        with self.assertRaisesRegex(AssertionError, "Outcome count"):
            runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_missing_candidate_outcome_is_refused(self):
        (self.output / "egui/outcome.json").unlink()
        with self.assertRaisesRegex(AssertionError, "Outcome count"):
            runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_wrong_recorded_order_is_refused(self):
        self.write("selected-candidates.json", ["egui", "egui_reduced"])
        with self.assertRaises(AssertionError):
            runner.verify(self.output, self.candidates, comparison=True, desktop_checks=True)

    def test_sequential_runner_stops_after_failed_desktop_cleanup(self):
        outcome = self.valid_outcome("egui", comparison=False)
        outcome["desktop_integration"]["cleanup"]["status"] = "failed"
        self.write("egui/outcome.json", outcome)
        environment = dict(SELECTED_FRAMEWORKS='["egui", "gtk"]', CARGO_TARGET_DIR="target-fixture",
                           COMPARISON="false", DESKTOP_CHECKS="true", REDUCED_CONTROL="false")
        with patch.dict(os.environ, environment), \
                patch.object(runner.sys, "argv", ["run_native_candidates.py", "--output", str(self.output)]), \
                patch.object(runner.subprocess, "Popen", return_value=Mock(wait=Mock(return_value=0))) as launch:
            self.assertEqual(runner.main(), 0)  # Evidence first; --verify-only fails afterward.
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(json.loads((self.output / "failed-candidates.json").read_text()), ["egui"])
        self.assertEqual(json.loads((self.output / "stopped-after.json").read_text())["name"], "egui")

    def run_control(self, theme, launch):
        output = self.output / "control-run"
        environment = dict(SELECTED_FRAMEWORKS='["egui"]', CARGO_TARGET_DIR="target-fixture",
                           COMPARISON="false", DESKTOP_CHECKS="true", REDUCED_CONTROL="true", REPETITION="1")
        with patch.dict(os.environ, environment), \
                patch.object(runner.sys, "argv", ["run_native_candidates.py", "--output", str(output)]), \
                patch.object(runner, "SystemTheme", return_value=theme), \
                patch.object(runner.subprocess, "Popen", side_effect=launch) as spawned:
            self.assertEqual(runner.main(), 0)
        return output, spawned

    def test_control_setup_failure_prevents_launch_and_further_candidates(self):
        theme = Mock(set=Mock(side_effect=RuntimeError("portal unavailable")))
        output, spawned = self.run_control(theme, Mock())
        spawned.assert_not_called()
        theme.restore.assert_called_once()
        outcome = json.loads((output / "egui_reduced/outcome.json").read_text())
        self.assertEqual(outcome["status"], "failed")
        self.assertEqual(outcome["measurement_profile"], "diagnostic-reduced")
        self.assertEqual(outcome["control_system_theme"]["status"], "environment_error")
        self.assertEqual(outcome["phases"], {})
        self.assertTrue((output / "stopped-after.json").is_file())

    def test_control_restores_light_prerequisite_before_normal_primary_launch(self):
        events = []
        theme = Mock(snapshot=Mock(side_effect=lambda: events.append("snapshot")),
                     set=Mock(side_effect=lambda value: events.append(f"set-{value}") or {"theme": value}),
                     read=Mock(side_effect=lambda: events.append("read") or {"theme": "light"}),
                     restore=Mock(side_effect=lambda: events.append("restore")))
        def launch(command):
            name = command[command.index("--name") + 1]
            output = Path(command[command.index("--output") + 1])
            events.append(f"launch-{name}")
            output.mkdir(parents=True, exist_ok=True)
            (output / "outcome.json").write_text(json.dumps(self.valid_outcome(name, comparison=False)))
            return Mock(wait=Mock(return_value=0))
        output, spawned = self.run_control(theme, launch)
        self.assertEqual(spawned.call_count, 2)
        self.assertEqual(events, ["snapshot", "set-light", "launch-egui_reduced", "read", "restore", "launch-egui"])
        runner.verify(output, self.candidates, comparison=False, desktop_checks=True)

    def test_control_launch_failure_still_restores_and_records_no_pass(self):
        theme = Mock(set=Mock(return_value={"theme": "light"}), read=Mock(return_value={"theme": "light"}))
        output, spawned = self.run_control(theme, FileNotFoundError("probe executable unavailable"))
        spawned.assert_called_once()
        theme.restore.assert_called_once()
        outcome = json.loads((output / "egui_reduced/outcome.json").read_text())
        self.assertEqual(outcome["status"], "failed")
        self.assertEqual(outcome["control_system_theme"]["cleanup"]["status"], "passed")
        self.assertTrue((output / "egui_reduced/runner-error.json").is_file())


class ControlThemeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.theme = Mock(set=Mock(return_value={"theme": "light"}), read=Mock(return_value={"theme": "light"}))
        self.control = runner.ControlTheme(self.output, theme=self.theme)

    def test_snapshot_set_read_and_restore_are_recorded_without_desktop_pass(self):
        self.control.prepare()
        self.assertTrue(self.control.close())
        self.theme.snapshot.assert_called_once()
        self.theme.set.assert_called_once_with("light")
        self.theme.read.assert_called_once()
        self.theme.restore.assert_called_once()
        evidence = json.loads((self.output / "control-system-theme.json").read_text())
        self.assertEqual(evidence, self.control.result)
        self.assertEqual(evidence["profile"], "control-system-theme-v1")
        self.assertNotIn("clipboard", evidence)
        self.assertNotIn("desktop_integration", evidence)

    def test_failed_snapshot_does_not_mutate_or_restore_unknown_setting(self):
        self.theme.snapshot.side_effect = RuntimeError("cannot read OS preference")
        with self.assertRaises(RuntimeError):
            self.control.prepare()
        self.assertFalse(self.control.close())
        self.theme.set.assert_not_called()
        self.theme.restore.assert_not_called()
        self.assertEqual(self.control.result["cleanup"]["status"], "not_needed")

    def test_failed_set_is_restored_but_never_valid(self):
        self.theme.set.side_effect = RuntimeError("setting failed")
        with self.assertRaises(RuntimeError):
            self.control.prepare()
        self.assertFalse(self.control.close())
        self.theme.restore.assert_called_once()
        self.assertEqual(self.control.result["status"], "environment_error")

    def test_unverified_light_is_refused_before_control_run(self):
        self.theme.set.return_value = {"theme": "dark"}
        with self.assertRaisesRegex(RuntimeError, "not verified light"):
            self.control.prepare()
        self.assertFalse(self.control.close())

    def test_appearance_change_during_control_invalidates_pair_but_restores(self):
        self.control.prepare()
        self.theme.read.return_value = {"theme": "dark"}
        self.assertFalse(self.control.close())
        self.theme.restore.assert_called_once()
        self.assertEqual(self.control.result["cleanup"]["status"], "passed")
        self.assertEqual(self.control.result["status"], "environment_error")

    def test_failed_restoration_invalidates_control(self):
        self.control.prepare()
        self.theme.restore.side_effect = RuntimeError("restore failed")
        self.assertFalse(self.control.close())
        self.assertEqual(self.control.result["cleanup"]["status"], "failed")
        self.assertEqual(self.control.result["status"], "environment_error")


if __name__ == "__main__":
    unittest.main()
