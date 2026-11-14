"""Synthetic, temporary fixtures only: never generate published measurements."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

import build_desktop_site_data as builder


class DesktopSiteDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.series = self.root / "measurements/test-series"
        self.series.mkdir(parents=True)
        self.summaries, self.invocations, self.ab = [], [], []

    def base(self, **changes):
        row = dict(os="ubuntu-24.04", framework="egui", run_id="123", source_commit="a" * 40,
                   source_hash="", source_manifest_sha256="b" * 64, build_inputs_sha256="c" * 64,
                   image_version="image-a", measurement_profile="desktop-integrated",
                   desktop_profile="desktop-acceptance-v1", desktop_status="passed")
        row.update(changes)
        return row

    def summary(self, **changes):
        return self.base(phase="comparison", scope="primary", repetitions="3", failed_repetitions="0",
                         primary_metric="Linux PSS", primary_median_mib="123.45", primary_min_mib="120.10",
                         primary_max_mib="126.09", cpu_median_percent="0.00000", **changes)

    def invocation(self, case="normal", *, evidence=True, **changes):
        row = self.base(repetition="1", case=case, startup_theme="light" if case == "normal" else "dark",
                        startup_theme_status="passed", live_theme_status="passed", clipboard_status="passed",
                        desktop_cleanup_status="passed", desktop_evidence_status="complete", status="diagnostic_passed",
                        cleanup_status="clean", reason="", evidence_errors="")
        row.update(changes)
        if evidence:
            directory = self.root / "measurements" / f"native-{row['run_id']}" / f"r{row['repetition']}" / row["os"]
            if case == "dark-startup":
                directory /= "dark"
            directory /= row["framework"]
            directory.mkdir(parents=True, exist_ok=True)
            for name in ("outcome.json", "desktop-integration.json"):
                (directory / name).write_text("{}", encoding="utf-8")
            # The importer tests validate real PNG content. This builder only links
            # existing imported evidence; this filename exists in a private fixture.
            (directory / "desktop-startup.png").write_bytes(b"synthetic test fixture")
        return row

    def build(self):
        for name, rows, fallback in (("summary.csv", self.summaries, self.summary()),
                                     ("desktop-acceptance.csv", self.invocations, self.invocation(evidence=False))):
            fields = list(dict.fromkeys(key for row in [fallback, *rows] for key in row))
            with (self.series / name).open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        (self.series / "paired-egui-ab.json").write_text(json.dumps(dict(schema_version=1, summary=self.ab)), encoding="utf-8")
        return builder.build(self.series, root=self.root)

    def egui(self, data):
        return data["platforms"][0]["candidates"][0]

    def test_empty_series_keeps_all_missing_candidates_without_zero_values(self):
        data = self.build()
        self.assertEqual(len(data["platforms"]), 3)
        self.assertTrue(all(len(platform["candidates"]) == 5 for platform in data["platforms"]))
        self.assertEqual(self.egui(data)["experiments"], [])
        self.assertEqual(data["paired_ab"], [])

    def test_measurement_values_and_provenance_are_preserved(self):
        self.summaries = [self.summary()]
        experiment = self.egui(self.build())["experiments"][0]
        self.assertEqual(experiment["measurements"][0], self.summaries[0])
        self.assertEqual(experiment["acceptance"]["status"], "not_run")
        self.assertEqual(experiment["identity"]["source_commit"], "a" * 40)
        self.assertTrue(experiment["links"]["run"].endswith("/123"))

    def test_smoke_can_be_verified_without_inventing_memory_samples(self):
        self.invocations = [self.invocation(), self.invocation("dark-startup")]
        experiment = self.egui(self.build())["experiments"][0]
        self.assertEqual(experiment["measurements"], [])
        self.assertEqual(experiment["acceptance"]["status"], "fully_verified")
        self.assertEqual(experiment["acceptance"]["normal_invocations"], 1)
        self.assertEqual(experiment["acceptance"]["dark_invocations"], 1)

    def test_light_only_is_incomplete_not_fully_verified(self):
        self.invocations = [self.invocation()]
        result = self.egui(self.build())["experiments"][0]["acceptance"]
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["startup_dark"], "not_run")

    def test_same_build_partial_normal_repetitions_preserve_memory_and_observed_passes(self):
        self.summaries = [{**self.summary(), "repetitions": "1"}]
        self.invocations = [self.invocation(repetition="2")]
        self.invocations.extend(self.invocation("dark-startup", repetition=str(rep)) for rep in (1, 2, 3))
        experiment = self.egui(self.build())["experiments"][0]
        result = experiment["acceptance"]
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["repetition_coverage"], "incomplete")
        self.assertEqual(result["normal_repetitions"], [2])
        self.assertEqual(result["dark_repetitions"], [1, 2, 3])
        self.assertEqual(result["missing_cases"], [{"case": "normal", "repetition": 1},
                                                   {"case": "normal", "repetition": 3}])
        self.assertEqual(result["duplicate_cases"], [])
        self.assertEqual((result["normal_invocations"], result["dark_invocations"]), (1, 3))
        for field in ("startup_light", "startup_dark", *builder.CHECKS, "provenance"):
            self.assertEqual(result[field], "passed", field)
        self.assertEqual(experiment["measurements"], self.summaries)
        self.assertEqual(len(experiment["invocations"]), 4)

    def test_equal_case_counts_cannot_hide_mismatched_repetitions(self):
        self.invocations = [self.invocation(repetition="1"), self.invocation("dark-startup", repetition="2")]
        result = self.egui(self.build())["experiments"][0]["acceptance"]
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["missing_cases"], [{"case": "normal", "repetition": 2},
                                                   {"case": "dark-startup", "repetition": 1}])
        self.assertEqual(result["startup_light"], "passed")
        self.assertEqual(result["startup_dark"], "passed")

    def test_duplicate_case_prevents_fully_verified_despite_matching_repetition_sets(self):
        for case in ("normal", "dark-startup"):
            with self.subTest(case=case):
                self.invocations = [self.invocation(), self.invocation("dark-startup"), self.invocation(case)]
                result = self.egui(self.build())["experiments"][0]["acceptance"]
                self.assertEqual(result["status"], "incomplete")
                self.assertEqual(result["normal_repetitions"], result["dark_repetitions"])
                self.assertEqual(result["missing_cases"], [])
                self.assertEqual(result["duplicate_cases"], [{"case": case, "repetition": 1, "count": 2}])
                self.assertEqual(result["startup_light"], "passed")
                self.assertEqual(result["startup_dark"], "passed")

    def test_missing_build_provenance_prevents_fully_verified_label(self):
        for field in ("source_manifest_sha256", "build_inputs_sha256", "image_version"):
            with self.subTest(field=field):
                self.invocations = [self.invocation(**{field: ""}), self.invocation("dark-startup", **{field: ""})]
                result = self.egui(self.build())["experiments"][0]["acceptance"]
                self.assertEqual(result["status"], "incomplete")
                self.assertEqual(result["provenance"], "incomplete")

    def test_process_cleanup_is_distinct_from_settings_cleanup(self):
        self.invocations = [self.invocation(cleanup_status="unknown"), self.invocation("dark-startup")]
        result = self.egui(self.build())["experiments"][0]["acceptance"]
        self.assertEqual(result["cleanup"], "passed")
        self.assertEqual(result["process_cleanup"], "incomplete")
        self.assertEqual(result["status"], "incomplete")

    def test_different_commit_cannot_supply_missing_dark_startup(self):
        self.invocations = [self.invocation(), self.invocation("dark-startup", source_commit="b" * 40)]
        experiments = self.egui(self.build())["experiments"]
        self.assertEqual(len(experiments), 2)
        self.assertTrue(all(experiment["acceptance"]["status"] == "incomplete" for experiment in experiments))

    def test_different_build_identity_cannot_supply_dark_startup(self):
        self.invocations = [self.invocation(), self.invocation("dark-startup", build_inputs_sha256="different")]
        self.assertTrue(all(experiment["acceptance"]["status"] == "incomplete"
                            for experiment in self.egui(self.build())["experiments"]))

    def test_runner_image_drift_cannot_borrow_other_images_dark_startup(self):
        self.summaries = [{**self.summary(), "repetitions": "1"},
                          {**self.summary(image_version="image-b"), "repetitions": "2"}]
        self.invocations = [self.invocation(), self.invocation("dark-startup"),
                            self.invocation(repetition="2", image_version="image-b"),
                            self.invocation(repetition="3", image_version="image-b")]
        experiments = {entry["identity"]["image_version"]: entry
                       for entry in self.egui(self.build())["experiments"]}
        self.assertEqual(set(experiments), {"image-a", "image-b"})
        self.assertEqual(experiments["image-a"]["acceptance"]["status"], "fully_verified")
        self.assertEqual(experiments["image-b"]["acceptance"]["status"], "incomplete")
        self.assertEqual(experiments["image-b"]["acceptance"]["startup_dark"], "not_run")
        self.assertEqual(experiments["image-b"]["measurements"][0]["repetitions"], "2")

    def test_dark_startup_each_repetition_qualifies_images_without_inflating_sample_n(self):
        self.summaries = [{**self.summary(), "repetitions": "1"},
                          {**self.summary(image_version="image-b"), "repetitions": "2"}]
        for image, repetitions in (("image-a", ("1",)), ("image-b", ("2", "3"))):
            for repetition in repetitions:
                self.invocations.extend(self.invocation(case, repetition=repetition, image_version=image)
                                        for case in ("normal", "dark-startup"))
        experiments = {entry["identity"]["image_version"]: entry
                       for entry in self.egui(self.build())["experiments"]}
        self.assertEqual(set(experiments), {"image-a", "image-b"})
        for image, count in (("image-a", 1), ("image-b", 2)):
            with self.subTest(image=image):
                experiment = experiments[image]
                self.assertEqual(experiment["acceptance"]["status"], "fully_verified")
                self.assertEqual(experiment["acceptance"]["normal_invocations"], count)
                self.assertEqual(experiment["acceptance"]["dark_invocations"], count)
                self.assertEqual(experiment["measurements"][0]["repetitions"], str(count))
                self.assertEqual(len(experiment["invocations"]), 2 * count)

    def test_failed_clipboard_is_visible_despite_other_passed_fields(self):
        self.invocations = [self.invocation(clipboard_status="failed", status="failed"), self.invocation("dark-startup")]
        acceptance = self.egui(self.build())["experiments"][0]["acceptance"]
        self.assertEqual(acceptance["status"], "failed")
        self.assertEqual(acceptance["clipboard"], "failed")

    def test_environment_error_stays_distinct(self):
        self.invocations = [self.invocation(desktop_status="environment_error", startup_theme="", status="failed")]
        self.assertEqual(self.egui(self.build())["experiments"][0]["acceptance"]["status"], "environment_error")

    def test_missing_raw_evidence_prevents_fully_verified_label(self):
        self.invocations = [self.invocation(evidence=False), self.invocation("dark-startup", evidence=False)]
        experiment = self.egui(self.build())["experiments"][0]
        self.assertEqual(experiment["acceptance"]["status"], "incomplete")
        self.assertEqual(experiment["invocations"][0]["links"]["screenshots"], [])

    def test_links_only_reference_existing_snapshots(self):
        self.invocations = [self.invocation()]
        links = self.egui(self.build())["experiments"][0]["invocations"][0]["links"]
        self.assertEqual(len(links["screenshots"]), 1)
        self.assertTrue(links["screenshots"][0]["url"].endswith("/measurements/native-123/r1/ubuntu-24.04/egui/desktop-startup.png"))

    def test_reduced_and_historical_rows_cannot_enter_primary_table(self):
        reduced = self.summary()
        reduced.update(framework="egui_reduced", measurement_profile="diagnostic-reduced", scope="control")
        old = self.summary()
        old.update(measurement_profile="", scope="historical")
        self.summaries = [reduced, old]
        self.assertEqual(self.egui(self.build())["experiments"], [])

    def test_nonfinite_or_missing_measurement_is_refused(self):
        for value in ("", "NaN", "inf", "-1"):
            with self.subTest(value=value):
                row = self.summary()
                row["primary_median_mib"] = value
                self.summaries = [row]
                with self.assertRaises(ValueError):
                    self.build()

    def test_duplicate_summary_is_not_silently_overwritten(self):
        self.summaries = [self.summary(), self.summary()]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.build()

    def test_paired_delta_preserves_negative_values_and_excludes_minimized(self):
        row = self.base(phase="comparison", primary_metric="Linux PSS", paired_repetitions=3,
                        primary_delta_median_mib=-1.25, primary_delta_min_mib=-2.5, primary_delta_max_mib=0)
        self.ab = [row, {**row, "phase": "minimized"}]
        result = self.build()["paired_ab"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["primary_delta_median_mib"], -1.25)
        self.assertEqual(result[0]["paired_repetitions"], 3)
        self.assertEqual(result[0]["platform"], "linux")

    def test_paired_delta_requires_named_metric_and_ordered_range(self):
        row = self.base(phase="comparison", primary_metric="Linux PSS", paired_repetitions=3,
                        primary_delta_median_mib=-1.25, primary_delta_min_mib=-2.5, primary_delta_max_mib=0)
        for changes in ({"primary_metric": " "}, {"primary_delta_median_mib": 1}, {"primary_delta_min_mib": 0}):
            with self.subTest(changes=changes):
                self.ab = [{**row, **changes}]
                with self.assertRaises(ValueError):
                    self.build()

    def test_unknown_os_and_unsafe_artifact_identity_are_refused(self):
        self.summaries = [self.summary(os="unknown-runner")]
        with self.assertRaisesRegex(ValueError, "Unknown runner"):
            self.build()
        self.summaries = []
        self.invocations = [self.invocation(evidence=False, run_id="../../escape")]
        with self.assertRaisesRegex(ValueError, "artifact identity"):
            self.build()

    def test_check_accepts_reproducible_published_data_without_rewriting(self):
        self.build()
        self.assertEqual(builder.main([str(self.series)], root=self.root), 0)
        output = self.root / "data/desktop-results.json"
        before = output.stat().st_mtime_ns
        self.assertEqual(builder.main([str(self.series), "--check"], root=self.root), 0)
        self.assertEqual(output.stat().st_mtime_ns, before)

    def test_check_rejects_stale_data_without_overwriting_it(self):
        self.build()
        output = self.root / "review.json"
        output.write_text('{"schema_version": 0}\n', encoding="utf-8")
        self.assertEqual(builder.main([str(self.series), "--output", str(output), "--check"], root=self.root), 1)
        self.assertEqual(output.read_text(encoding="utf-8"), '{"schema_version": 0}\n')

    def test_check_does_not_create_a_missing_output(self):
        self.build()
        self.assertEqual(builder.main([str(self.series), "--check"], root=self.root), 1)
        self.assertFalse((self.root / "data/desktop-results.json").exists())


if __name__ == "__main__":
    unittest.main()
