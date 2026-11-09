"""Host-free tests for evidence preservation and mixed-profile refusal.

All generated outcomes/screenshots below are synthetic test fixtures, never
published measurements. A separate regression replays the committed history.
"""
import copy
import csv
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import import_native_run as importer


class ImportNativeRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.artifacts = self.base / "artifacts"
        self.artifacts.mkdir()
        self.source = self.artifacts / "native-ubuntu-24.04-123-r1"
        self.source.mkdir()

    def json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def outcome(self, framework="egui", profile="desktop-integrated", primary=110):
        outcome = dict(
            name=framework, status="comparison_passed", cleanup_status="clean", comparison_requested=True,
            environment=dict(commit="a" * 40, run_id="123", repetition="1", image_version="image-1"),
            primary_memory_metric="Linux PSS", memory_metric="Linux RSS",
            phases={"comparison": dict(status="passed", summary=dict(
                family_primary_mib=dict(median=primary, p95=primary + 1),
                family_rss_mib=dict(median=primary + 20), observed_cpu_percent_one_core=.02,
                seconds=121.2, sample_intervals=120))})
        if profile is not None:
            outcome["measurement_profile"] = profile
        if profile == "diagnostic-reduced":
            outcome["control_system_theme"] = dict(
                schema_version=1, profile="control-system-theme-v1", status="passed", requested="light",
                observed=dict(theme="light"), observed_after=dict(theme="light"), cleanup=dict(status="passed"))
        if profile == "desktop-integrated":
            def appearance(theme, name):
                return dict(status="passed", expected=theme, mean_client_luma=230 if theme == "light" else 40,
                            screenshot=name, same_window_and_pid=True, attempts=1)
            startup = appearance("light", "desktop-startup.png")
            transitions = [appearance("dark", "desktop-live-1-dark.png"), appearance("light", "desktop-live-2-light.png")]
            for transition in transitions:
                transition.update(luminance_delta=190, system_setting=dict(source="synthetic-test", theme=transition["expected"]))
            outcome["desktop_integration"] = dict(
                schema_version=1, profile="desktop-acceptance-v1", status="passed",
                application_process=dict(pid=42, created=1000.0), application_window=dict(pid=42, id=123),
                system_theme_setup=dict(status="passed", requested="light", observed=dict(theme="light")),
                startup_theme=startup, live_theme=dict(status="passed", transitions=transitions),
                clipboard=dict(status="passed", expected_utf8="München — Привет ✓", copied_utf8="München — Привет ✓",
                               sentinel_utf8="unrelated-sentinel", sentinel_verified=True, probe_helpers_reaped_before_idle=True,
                               pasted_screenshot="desktop-clipboard-pasted.png", restored_fixture_screenshot="desktop-ready-for-idle.png"),
                cleanup=dict(status="passed", errors=[]))
        return outcome

    def save(self, outcome, source=None):
        directory = (source or self.source) / outcome["name"]
        self.json(directory / "outcome.json", outcome)
        if "desktop_integration" in outcome:
            desktop = outcome["desktop_integration"]
            self.json(directory / "desktop-integration.json", desktop)
            for name in ("desktop-startup.png", "desktop-live-1-dark.png", "desktop-live-2-light.png",
                         "desktop-clipboard-pasted.png", "desktop-ready-for-idle.png"):
                Image.new("RGB", (100, 100), (40, 40, 40) if "dark" in name else (230, 230, 230)).save(directory / name)
        if "control_system_theme" in outcome:
            self.json(directory / "control-system-theme.json", outcome["control_system_theme"])
        return directory

    def rows(self, source=None, repetition=1):
        return list(importer.rows_for("123", "ubuntu-24.04", repetition, source or self.source))

    def test_complete_desktop_evidence_qualifies_for_primary_summary(self):
        self.save(self.outcome())
        row = self.rows()[0]
        self.assertEqual(row["eligibility"], "primary")
        self.assertEqual(row["desktop_evidence_status"], "complete")
        summary = importer.aggregate([row], {})[0]
        self.assertEqual(summary["primary_median_mib"], 110)
        self.assertTrue(summary["follows_dark_mode"])
        self.assertEqual(summary["scope"], "primary")

    def test_missing_historical_profile_is_not_relabelled_as_desktop(self):
        self.save(self.outcome(profile=None))
        row = self.rows()[0]
        self.assertEqual(row["measurement_profile"], "")
        self.assertEqual(row["desktop_status"], "")
        self.assertEqual(row["eligibility"], "historical")
        summary = importer.aggregate([row], {("ubuntu-24.04", "egui"): False})[0]
        self.assertEqual(summary["measurement_profile"], "")
        self.assertEqual(summary["desktop_status"], "")
        self.assertIs(summary["follows_dark_mode"], False)

    def test_new_explicit_ui_only_profile_is_not_full_desktop(self):
        self.save(self.outcome(profile="legacy-ui-only"))
        row = self.rows()[0]
        self.assertEqual(row["eligibility"], "excluded")
        self.assertEqual(importer.aggregate([row], {}), [])

    def test_top_level_pass_does_not_hide_skipped_or_failed_checks(self):
        for key in ("startup_theme", "live_theme", "clipboard", "cleanup"):
            for status in ("failed", "not_run", "environment_error"):
                with self.subTest(key=key, status=status):
                    outcome = self.outcome()
                    outcome["desktop_integration"][key]["status"] = status
                    self.save(outcome)
                    row = self.rows()[0]
                    self.assertEqual(row["desktop_status"], "passed")
                    self.assertEqual(row["eligibility"], "excluded")
                    self.assertEqual(importer.aggregate([row], {}), [])

    def test_missing_desktop_object_cannot_become_historical(self):
        outcome = self.outcome()
        del outcome["desktop_integration"]
        self.save(outcome)
        row = self.rows()[0]
        self.assertEqual(row["desktop_evidence_status"], "missing")
        self.assertEqual(row["eligibility"], "excluded")

    def test_missing_or_disagreeing_sidecar_is_excluded(self):
        outcome = self.outcome()
        directory = self.save(outcome)
        (directory / "desktop-integration.json").unlink()
        self.assertIn("sidecar", self.rows()[0]["exclusion_reason"])
        self.json(directory / "desktop-integration.json", {"status": "passed"})
        self.assertEqual(self.rows()[0]["eligibility"], "excluded")

    def test_missing_png_or_path_escape_is_not_evidence(self):
        outcome = self.outcome()
        directory = self.save(outcome)
        (directory / "desktop-live-1-dark.png").unlink()
        self.assertEqual(self.rows()[0]["eligibility"], "excluded")
        outcome["desktop_integration"]["startup_theme"]["screenshot"] = "../outside.png"
        self.save(outcome)
        self.assertFalse(importer.screenshot_present(directory, "../outside.png"))
        self.assertEqual(self.rows()[0]["eligibility"], "excluded")

    def test_live_theme_requires_actual_transitions_and_same_window(self):
        for change in (dict(same_window_and_pid=False), dict(luminance_delta=0), dict(mean_client_luma=230)):
            with self.subTest(change=change):
                outcome = self.outcome()
                outcome["desktop_integration"]["live_theme"]["transitions"][0].update(change)
                self.save(outcome)
                self.assertEqual(self.rows()[0]["eligibility"], "excluded")

    def test_reported_dark_luma_cannot_pass_with_a_light_screenshot(self):
        directory = self.save(self.outcome())
        Image.new("RGB", (100, 100), (230, 230, 230)).save(directory / "desktop-live-1-dark.png")
        self.assertEqual(self.rows()[0]["eligibility"], "excluded")

    def test_clipboard_negative_control_and_helper_cleanup_are_required(self):
        for change in (dict(copied_utf8="unrelated-sentinel"), dict(sentinel_verified=False),
                       dict(probe_helpers_reaped_before_idle=False), dict(sentinel_utf8="München — Привет ✓")):
            with self.subTest(change=change):
                outcome = self.outcome()
                outcome["desktop_integration"]["clipboard"].update(change)
                self.save(outcome)
                self.assertEqual(self.rows()[0]["eligibility"], "excluded")

    def test_desktop_gate_failure_without_samples_remains_a_failed_requested_row(self):
        outcome = self.outcome()
        outcome.update(status="failed", phases={}, reason="Portal unavailable")
        outcome["desktop_integration"]["status"] = "environment_error"
        self.save(outcome)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["phase"], "comparison")
        self.assertEqual(rows[0]["primary_median_mib"], "")
        self.assertEqual(rows[0]["reason"], "Portal unavailable")
        self.assertEqual(rows[0]["eligibility"], "excluded")
        self.assertEqual(importer.aggregate(rows, {}), [])

    def test_diagnostic_only_is_acceptance_not_a_failed_memory_comparison(self):
        outcome = self.outcome()
        outcome.update(status="diagnostic_passed", comparison_requested=False, phases={})
        self.save(outcome, self.source / "dark")
        self.assertEqual(self.rows(), [])
        rows = list(importer.acceptance_rows("123", "ubuntu-24.04", 1, self.source))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["case"], "dark-startup")
        self.assertEqual(rows[0]["desktop_evidence_status"], "complete")

    def test_failed_status_and_unclean_processes_never_enter_primary_summary(self):
        for change in (dict(status="failed"), dict(cleanup_status="unknown"), dict(comparison_requested=False)):
            with self.subTest(change=change):
                outcome = self.outcome()
                outcome.update(change)
                self.save(outcome)
                self.assertEqual(importer.aggregate(self.rows(), {}), [])

    def test_short_or_non_numeric_samples_are_excluded(self):
        for change in (dict(sample_intervals=119), dict(seconds=119), dict(observed_cpu_percent_one_core="NaN"),
                       dict(family_primary_mib=dict(median="invalid", p95=1))):
            with self.subTest(change=change):
                outcome = self.outcome()
                outcome["phases"]["comparison"]["summary"].update(change)
                self.save(outcome)
                self.assertEqual(importer.aggregate(self.rows(), {}), [])

    def test_json_nan_is_rejected_instead_of_poisoning_statistics(self):
        outcome = self.outcome(profile=None)
        outcome["phases"]["comparison"]["summary"]["observed_cpu_percent_one_core"] = float("nan")
        self.save(outcome)
        with self.assertRaisesRegex(ValueError, "Non-finite JSON"):
            self.rows()

    def test_reduced_control_is_separate_and_pair_has_measured_deltas(self):
        self.save(self.outcome(primary=110))
        self.save(self.outcome("egui_reduced", "diagnostic-reduced", primary=100))
        rows = self.rows()
        self.assertEqual([row["framework"] for row in importer.aggregate(rows, {})], ["egui"])
        self.assertEqual([row["framework"] for row in importer.aggregate(rows, {}, controls=True)], ["egui_reduced"])
        report = importer.paired_egui(rows)
        self.assertEqual(len(report["pairs"]), 1)
        self.assertEqual(report["pairs"][0]["status"], "paired")
        self.assertEqual(report["pairs"][0]["primary_delta_mib"], 10)
        self.assertEqual(report["pairs"][0]["primary_delta_percent"], 10)
        self.assertEqual(report["summary"][0]["paired_repetitions"], 1)

    def test_reduced_name_with_wrong_profile_cannot_enter_either_summary(self):
        self.save(self.outcome("egui_reduced", "legacy-ui-only", primary=100))
        rows = self.rows()
        self.assertEqual(importer.aggregate(rows, {}), [])
        self.assertEqual(importer.aggregate(rows, {}, controls=True), [])

    def test_reduced_control_requires_verified_common_light_theme_and_cleanup(self):
        for change in (dict(status="environment_error"), dict(observed_after=dict(theme="dark")),
                       dict(cleanup=dict(status="failed"))):
            with self.subTest(change=change):
                outcome = self.outcome("egui_reduced", "diagnostic-reduced")
                outcome["control_system_theme"].update(change)
                self.save(outcome)
                self.assertEqual(importer.aggregate(self.rows(), {}, controls=True), [])
        outcome = self.outcome("egui_reduced", "diagnostic-reduced")
        del outcome["control_system_theme"]
        self.save(outcome)
        self.assertEqual(importer.aggregate(self.rows(), {}, controls=True), [])

    def test_different_run_commit_build_profile_image_and_metric_are_not_aggregated(self):
        self.save(self.outcome())
        base = self.rows()[0]
        for key in ("run_id", "source_commit", "source_hash", "source_manifest_sha256", "build_inputs_sha256",
                    "measurement_profile", "desktop_profile", "image_version", "primary_metric", "rss_metric"):
            with self.subTest(field=key):
                changed = {**base, key: "different", "repetition": 2, "primary_median_mib": 210}
                summary = importer.aggregate([base, changed], {})
                self.assertEqual(len(summary), 2)
                self.assertEqual(sorted(row["primary_median_mib"] for row in summary), [110, 210])

    def test_ab_never_pairs_across_source_commit_or_image(self):
        self.save(self.outcome())
        self.save(self.outcome("egui_reduced", "diagnostic-reduced", primary=100))
        rows = self.rows()
        for key in ("source_commit", "image_version", "source_manifest_sha256", "primary_metric", "run_id", "repetition"):
            with self.subTest(field=key):
                changed = copy.deepcopy(rows)
                changed[1][key] = "different"
                report = importer.paired_egui(changed)
                self.assertEqual(report["summary"], [])
                self.assertTrue(all(pair["status"] == "not_paired" for pair in report["pairs"]))

    def test_duplicate_repetition_is_an_error_not_extra_statistical_weight(self):
        self.save(self.outcome())
        row = self.rows()[0]
        with self.assertRaisesRegex(ValueError, "Duplicate measurement"):
            importer.aggregate([row, dict(row)], {})
        with self.assertRaisesRegex(ValueError, "Multiple measurement profiles"):
            importer.paired_egui([row, {**row, "measurement_profile": "legacy-ui-only"}])

    def test_run_or_repetition_identity_mismatch_is_excluded(self):
        for key in ("run_id", "repetition"):
            outcome = self.outcome()
            outcome["environment"][key] = "999"
            self.save(outcome)
            self.assertEqual(self.rows()[0]["eligibility"], "excluded")

    def test_dark_acceptance_cannot_relabel_a_different_run_or_repetition_as_current(self):
        for key in ("run_id", "repetition"):
            with self.subTest(key=key):
                outcome = self.outcome()
                outcome["environment"][key] = "999"
                self.save(outcome, self.source / "dark")
                row = list(importer.acceptance_rows("123", "ubuntu-24.04", 1, self.source))[0]
                self.assertEqual(row["desktop_status"], "passed")
                self.assertEqual(row["desktop_evidence_status"], "incomplete")
                self.assertIn(f"{key} differs", row["evidence_errors"])

    def test_native_process_cleanup_status_is_preserved_separately_from_desktop_cleanup(self):
        outcome = self.outcome()
        outcome["cleanup_status"] = "unknown"
        self.save(outcome)
        row = list(importer.acceptance_rows("123", "ubuntu-24.04", 1, self.source))[0]
        self.assertEqual(row["cleanup_status"], "unknown")
        self.assertEqual(row["desktop_cleanup_status"], "passed")

    def test_outcome_commit_must_match_recorded_build_source_for_memory_and_acceptance(self):
        self.save(self.outcome())
        build = self.source / "build"
        build.mkdir()
        (build / "source-commit.txt").write_text("b" * 40 + "\n", encoding="utf-8")
        self.assertEqual(self.rows()[0]["eligibility"], "excluded")
        row = list(importer.acceptance_rows("123", "ubuntu-24.04", 1, self.source))[0]
        self.assertEqual(row["desktop_evidence_status"], "incomplete")
        self.assertIn("source commit differs", row["evidence_errors"])

    def test_copy_preserves_desktop_build_dark_evidence_and_reproducible_samples(self):
        self.save(self.outcome())
        self.save(self.outcome(), self.source / "dark")
        self.save(self.outcome("egui_reduced", "diagnostic-reduced"))
        self.json(self.source / "selected-candidates.json", ["egui", "gtk"])
        self.json(self.source / "failed-candidates.json", ["egui"])
        self.json(self.source / "stopped-after.json", dict(name="egui", reason="unverified process cleanup"))
        build = self.source / "build"
        build.mkdir()
        for name in ("source-sha256.txt", "egui-features.txt", "egui-Cargo.lock", "libadwaita-version.txt"):
            (build / name).write_text(f"synthetic {name}\n", encoding="utf-8")
        (build / "unwanted.dll").write_bytes(b"not provenance")
        self.json(self.source / "egui" / "comparison-samples.json", [{"synthetic": True}])
        image = self.source / "egui" / "desktop-startup.png"
        (self.source / "dark" / "egui" / "diagnostic.png").write_bytes(image.read_bytes())
        for number in (1, 2):
            target = self.base / f"copy-{number}"
            importer.copy_evidence(self.source, target, 2, "ubuntu-24.04", self.base / "shots")
            self.assertTrue((target / "egui" / "desktop-integration.json").exists())
            self.assertTrue((target / "egui" / "desktop-ready-for-idle.png").exists())
            self.assertTrue((target / "dark" / "egui" / "desktop-integration.json").exists())
            self.assertTrue((target / "egui_reduced" / "outcome.json").exists())
            self.assertTrue((target / "build" / "libadwaita-version.txt").exists())
            self.assertTrue((target / "build" / "egui-features.txt").exists())
            self.assertFalse((target / "build" / "unwanted.dll").exists())
            self.assertEqual(importer.read_json(target / "stopped-after.json")["reason"], "unverified process cleanup")
            self.assertTrue((target / "selected-candidates.json").exists())
            self.assertTrue((target / "failed-candidates.json").exists())
        archives = [self.base / f"copy-{i}" / "egui" / "comparison-samples.json.gz" for i in (1, 2)]
        self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())
        self.assertEqual(json.loads(gzip.decompress(archives[0].read_bytes())), [{"synthetic": True}])

    def test_dark_screenshot_copy_does_not_require_a_successful_light_capture(self):
        directory = self.save(self.outcome(), self.source / "dark")
        (directory / "diagnostic.png").write_bytes((directory / "desktop-startup.png").read_bytes())
        importer.copy_evidence(self.source, self.base / "copy", 1, "ubuntu-24.04", self.base / "shots")
        self.assertTrue((self.base / "shots" / "egui-dark.png").exists())

    def test_build_identity_changes_with_locks_features_or_source_hashes_not_logs(self):
        build = self.source / "build"
        build.mkdir()
        for name in ("egui-Cargo.lock", "egui-features.txt", "source-sha256.txt"):
            with self.subTest(name=name):
                initial = importer.build_identity(self.source)
                (build / name).write_text("new input", encoding="utf-8")
                self.assertNotEqual(initial, importer.build_identity(self.source))
        initial = importer.build_identity(self.source)
        (build / "egui.log").write_text("timestamped compiler log", encoding="utf-8")
        self.assertEqual(initial, importer.build_identity(self.source))

    def test_different_actual_native_and_toolchain_versions_do_not_merge(self):
        self.save(self.outcome())
        build = self.source / "build"
        build.mkdir()
        for name in sorted(importer.VERSION_FILES):
            with self.subTest(name=name):
                path = build / name
                path.write_text("stable version 1\n", encoding="utf-8")
                before = self.rows()[0]
                path.write_text("stable version 2\n", encoding="utf-8")
                after = self.rows()[0]
                self.assertNotEqual(before["build_inputs_sha256"], after["build_inputs_sha256"])
                self.assertEqual(len(importer.aggregate([before, after], {})), 2)

    def test_duplicate_artifact_alias_and_zero_repetition_are_refused(self):
        duplicate = self.artifacts / "native-ubuntu-24.04-123"
        duplicate.mkdir()
        with self.assertRaisesRegex(ValueError, "Duplicate artifact"):
            list(importer.artifact_dirs(self.artifacts, "123"))
        duplicate.rmdir()
        (self.artifacts / "native-windows-2022-123-r0").mkdir()
        with self.assertRaisesRegex(ValueError, "Invalid artifact"):
            list(importer.artifact_dirs(self.artifacts, "123"))

    def test_all_failed_import_preserves_evidence_and_writes_empty_primary_summary(self):
        outcome = self.outcome()
        outcome.update(status="failed", phases={})
        self.save(outcome)
        output_root = self.base / "repository"
        with patch.object(importer, "ROOT", output_root), \
                patch.object(importer.sys, "argv", ["import_native_run.py", "123", str(self.artifacts), "desktop-test"]):
            self.assertEqual(importer.main(), 0)
        series = output_root / "measurements" / "desktop-test"
        with (series / "summary.csv").open(encoding="utf-8", newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])
        report = importer.read_json(series / "import-report.json")
        self.assertEqual(report["status"], "no_eligible_primary_rows")
        self.assertEqual(len(report["exclusions"]), 1)
        self.assertTrue((output_root / "measurements" / "native-123" / "r1" / "ubuntu-24.04" / "egui" / "desktop-startup.png").exists())
        self.assertTrue((series / "SHA256SUMS").exists())

    def test_cli_rejects_destination_traversal(self):
        with patch.object(importer.sys, "argv", ["import_native_run.py", "123", str(self.artifacts), "../escape"]):
            self.assertEqual(importer.main(), 2)

    def test_committed_historical_matrix_retains_all_original_summary_values(self):
        root = Path(__file__).resolve().parent.parent
        history = root / "measurements" / "native-42538198685"
        summary_path = root / "measurements" / "native-matrix-2026-11-09" / "summary.csv"
        if not history.is_dir() or not summary_path.exists():
            self.skipTest("Historical measurement corpus is not present")
        with summary_path.open(encoding="utf-8", newline="") as stream:
            expected = list(csv.DictReader(stream))
        rows = []
        for repetition in sorted(history.iterdir()):
            if repetition.is_dir() and repetition.name.startswith("r"):
                for runner in repetition.iterdir():
                    rows.extend(importer.rows_for("42538198685", runner.name, int(repetition.name[1:]), runner))
        dark = {(row["os"], row["framework"]): row["follows_dark_mode"] for row in expected}
        actual = {(row["os"], row["framework"], row["phase"]): row for row in importer.aggregate(rows, dark)}
        self.assertEqual(len(actual), len(expected))
        for old in expected:
            new = actual[(old["os"], old["framework"], old["phase"])]
            self.assertEqual(new["measurement_profile"], "")
            for key, value in old.items():
                self.assertEqual(str(new[key]), value, (old["os"], old["framework"], old["phase"], key))


if __name__ == "__main__":
    unittest.main()
