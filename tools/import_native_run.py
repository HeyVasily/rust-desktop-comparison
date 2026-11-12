#!/usr/bin/env python3
"""Import native-comparison artifacts without promoting incomplete desktop tests.

Usage: import_native_run.py RUN_ID ARTIFACT_DIR SERIES_NAME

ARTIFACT_DIR contains native-<runner>-<run-id>[-r<repetition>] directories.
Outcomes, deterministic gzipped samples, build provenance and all captures go to
measurements/native-<run-id>/r<k>/<runner>. Repetition-one light/dark screenshots
also retain the historical screenshots/native-<run-id>/<runner> layout.

The series directory receives runs.csv (including failed requested comparisons),
summary.csv (eligible primary/historical results only), controls.csv (reduced
diagnostic controls, never primary rankings), desktop-acceptance.csv (including
separate dark-startup runs), paired-egui-ab.json and import-report.json.
Missing historical profile metadata remains missing: old results are not
retroactively described as desktop-acceptance passes. Aggregates never combine
source revisions, build inputs, measurement profiles, images or memory metrics.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import sys
from pathlib import Path

ROOT = Path(os.environ.get("IMPORT_ROOT", Path(__file__).resolve().parent.parent))
FRAMEWORKS = ("egui", "gtk", "slint", "qt", "tauri", "egui_reduced")
OUTLIER_FRACTION = 0.10
BUILD_SUFFIXES = {".txt", ".json", ".log", ".lock", ".toml", ".rs", ".slint", ".h",
                  ".c", ".cpp", ".sha256", ".md", ".yaml", ".yml", ".py", ".js", ".css", ".html", ".csv"}
INPUT_SUFFIXES = {".lock", ".toml", ".rs", ".slint", ".h", ".c", ".cpp", ".py", ".js", ".css", ".html"}
VERSION_FILES = {"rust-version.txt", "cmake-version.txt", "gtk-version.txt", "gtk-rust-version.txt",
                 "libadwaita-version.txt", "native-versions.txt", "webview2-version.txt", "msys2-packages.txt",
                 "windows-gtk-runtime.json", "qt-runtime.txt", "linux-desktop-versions.txt"}
GROUP_FIELDS = ("os", "framework", "phase", "run_id", "source_commit", "source_hash",
                "source_manifest_sha256", "build_inputs_sha256", "measurement_profile",
                "desktop_profile", "control_theme_profile", "image_version", "primary_metric", "rss_metric")
DESKTOP_FIELDS = ("desktop_profile", "desktop_status", "startup_theme_status", "live_theme_status",
                  "clipboard_status", "desktop_cleanup_status", "desktop_evidence_status")
CONTROL_FIELDS = ("control_theme_profile", "control_theme_status", "control_theme_cleanup_status", "control_theme_evidence_status")
RUN_FIELDS = ("os", "framework", "phase", "repetition", "status", "cleanup", "run_id", "source_commit",
              "image_version", "primary_metric", "primary_median_mib", "primary_p95_mib", "rss_metric",
              "rss_median_mib", "cpu_percent_one_core", "elapsed_seconds", "intervals", "executable_bytes",
              "measurement_profile", *DESKTOP_FIELDS, *CONTROL_FIELDS, "source_hash", "source_manifest_sha256",
              "build_inputs_sha256", "phase_status", "comparison_requested", "eligibility", "exclusion_reason", "reason")
SUMMARY_FIELDS = ("os", "framework", "phase", "repetitions", "failed_repetitions", "primary_metric",
                  "primary_median_mib", "primary_min_mib", "primary_max_mib", "primary_spread_percent",
                  "outlier_repetitions", "rss_metric", "rss_median_mib", "rss_min_mib", "rss_max_mib",
                  "cpu_median_percent", "cpu_max_percent", "executable_bytes", "follows_dark_mode",
                  "run_id", "source_commit", "measurement_profile", "desktop_profile", "desktop_status",
                  *CONTROL_FIELDS, "image_version", "source_hash", "source_manifest_sha256", "build_inputs_sha256", "scope")
ACCEPTANCE_FIELDS = ("os", "framework", "repetition", "case", "status", "cleanup_status", "measurement_profile",
                     *DESKTOP_FIELDS, *CONTROL_FIELDS, "startup_theme", "run_id", "source_commit", "source_hash",
                     "source_manifest_sha256", "build_inputs_sha256", "image_version", "evidence_errors", "reason")


def read_json(path):
    # json.loads normally accepts NaN/Infinity, which must never enter rankings.
    def non_finite(value):
        raise ValueError(f"Non-finite JSON number {value} in {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=non_finite)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component(value):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value)) and value not in (".", "..")


def artifact_dirs(base: Path, run_id: str):
    pattern = re.compile(rf"native-(?P<runner>.+?)-{re.escape(run_id)}(?:-r(?P<rep>\d+))?$")
    seen = set()
    for path in sorted(base.iterdir()):
        match = pattern.fullmatch(path.name)
        if not match or not path.is_dir():
            continue
        runner, repetition = match["runner"], int(match["rep"] or 1)
        if path.is_symlink() or not component(runner) or repetition < 1:
            raise ValueError(f"Invalid artifact directory: {path}")
        key = runner, repetition
        if key in seen:
            raise ValueError(f"Duplicate artifact for {runner} repetition {repetition}")
        seen.add(key)
        yield runner, repetition, path


def regular_files(root):
    if not root.exists():
        return
    if root.is_symlink():
        raise ValueError(f"Symlink evidence directory is not accepted: {root}")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink evidence is not accepted: {path}")
        if path.is_file():
            yield path


def copy_file(source, target):
    if source.is_symlink():
        raise ValueError(f"Symlink evidence is not accepted: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_case(source, target):
    for item in regular_files(source):
        relative = item.relative_to(source)
        if item.name.endswith("-samples.json"):
            packed_path = target / (str(relative) + ".gz")
            packed_path.parent.mkdir(parents=True, exist_ok=True)
            # mtime=0 and no embedded filename make archives reproducible.
            with item.open("rb") as raw, packed_path.open("wb") as file, \
                    gzip.GzipFile(fileobj=file, mode="wb", mtime=0, filename="") as packed:
                shutil.copyfileobj(raw, packed)
        elif item.suffix in (".json", ".log", ".txt", ".png") or item.name.endswith("-samples.json.gz"):
            copy_file(item, target / relative)


def copy_evidence(source: Path, target: Path, repetition: int, runner: str, shots: Path):
    del runner  # Kept in the signature for callers of the historical importer.
    target.mkdir(parents=True, exist_ok=True)
    for name in ("selected-candidates.json", "failed-candidates.json", "stopped-after.json"):
        path = source / name
        if path.is_file():
            copy_file(path, target / name)
    for item in regular_files(source / "build"):
        if item.suffix.lower() in BUILD_SUFFIXES or item.name == "SHA256SUMS":
            copy_file(item, target / "build" / item.relative_to(source / "build"))
    for fw in FRAMEWORKS:
        copy_case(source / fw, target / fw)
        if repetition == 1 and (source / fw / "comparison.png").is_file():
            copy_file(source / fw / "comparison.png", shots / f"{fw}.png")
    # Preserve all dark-startup repetitions, not merely a boolean and r1 image.
    copy_case(source / "dark", target / "dark")
    if repetition == 1:
        for fw in FRAMEWORKS:
            path = source / "dark" / fw / "diagnostic.png"
            if path.is_file():
                copy_file(path, shots / f"{fw}-dark.png")


def build_identity(source):
    build = source / "build"
    manifest = build / "source-sha256.txt"
    inputs = {}
    for path in regular_files(build):
        # Hash stable inputs, not timestamped compiler/probe logs. The original
        # files are preserved too, so this grouping key remains independently auditable.
        if path.suffix in INPUT_SUFFIXES or "feature" in path.name.lower() or path == manifest or path.name in VERSION_FILES:
            inputs[path.relative_to(build).as_posix()] = digest(path)
    return dict(source_manifest_sha256=digest(manifest) if manifest.is_file() else "",
                build_inputs_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest() if inputs else "")


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def screenshot_present(directory, name):
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".png"):
        return False
    path = directory / name
    if not path.is_file() or path.is_symlink():
        return False
    with path.open("rb") as stream:
        return stream.read(8) == b"\x89PNG\r\n\x1a\n" and path.stat().st_size > 8


def captured_luminance_matches(directory, appearance):
    name = appearance.get("screenshot")
    if not screenshot_present(directory, name):
        return False
    # Lazy import keeps legacy imports standard-library-only. Desktop evidence
    # requires Pillow, already pinned by the native probe and checks workflows.
    from desktop_probe import content_luminance
    try:
        return abs(content_luminance(directory / name) - appearance["mean_client_luma"]) < .01
    except (OSError, ValueError, RuntimeError):
        return False


def desktop_metadata(outcome, directory):
    """Validate evidence structure, not just a top-level 'passed' label.

    This does not replace visual artifact inspection. It rejects partial tests,
    missing captures, sidecar/outcome disagreement and no-op clipboard copies.
    """
    result = outcome.get("desktop_integration")
    fields = dict.fromkeys(DESKTOP_FIELDS, "")
    errors = []
    if not isinstance(result, dict):
        if outcome.get("measurement_profile") == "desktop-integrated":
            fields["desktop_evidence_status"] = "missing"
            errors.append("desktop_integration is missing")
        return fields, errors
    fields.update(desktop_profile=result.get("profile", ""), desktop_status=result.get("status", ""),
                  startup_theme_status=result.get("startup_theme", {}).get("status", ""),
                  live_theme_status=result.get("live_theme", {}).get("status", ""),
                  clipboard_status=result.get("clipboard", {}).get("status", ""),
                  desktop_cleanup_status=result.get("cleanup", {}).get("status", ""))
    sidecar = directory / "desktop-integration.json"
    if not sidecar.is_file() or read_json(sidecar) != result:
        errors.append("desktop sidecar is missing or differs from outcome")
    if result.get("schema_version") != 1 or result.get("profile") != "desktop-acceptance-v1":
        errors.append("unknown desktop acceptance schema/profile")
    for label in ("desktop_status", "startup_theme_status", "live_theme_status", "clipboard_status", "desktop_cleanup_status"):
        if fields[label] != "passed":
            errors.append(f"{label}={fields[label] or 'missing'}")
    setup, startup = result.get("system_theme_setup", {}), result.get("startup_theme", {})
    initial = startup.get("expected")
    if initial not in ("light", "dark") or setup.get("status") != "passed" or setup.get("requested") != initial \
            or setup.get("observed", {}).get("theme") != initial:
        errors.append("initial system appearance was not verified")
    process, window = result.get("application_process", {}), result.get("application_window", {})
    if not finite(process.get("pid")) or not finite(process.get("created")) or not window.get("id") or not window.get("pid"):
        errors.append("application process/window identity is missing")

    def appearance_valid(appearance, expected):
        luma = appearance.get("mean_client_luma")
        return appearance.get("status") == "passed" and appearance.get("expected") == expected \
            and appearance.get("same_window_and_pid") is True and finite(luma) \
            and 0 <= luma <= 255 and (luma < 110 if expected == "dark" else luma > 170) \
            and captured_luminance_matches(directory, appearance)

    if not appearance_valid(startup, initial):
        errors.append("startup appearance evidence is incomplete")
    transitions = result.get("live_theme", {}).get("transitions", [])
    if not isinstance(transitions, list) or len(transitions) != 2:
        errors.append("two live appearance transitions are required")
    else:
        previous = startup.get("mean_client_luma")
        for index, (transition, expected) in enumerate(zip(transitions, ("dark" if initial == "light" else "light", initial)), 1):
            luma, delta = transition.get("mean_client_luma"), transition.get("luminance_delta")
            if not appearance_valid(transition, expected) or transition.get("system_setting", {}).get("theme") != expected \
                    or not all(finite(value) for value in (previous, luma, delta)) \
                    or delta <= 60 or abs(abs(luma - previous) - delta) > .01:
                errors.append(f"live appearance transition {index} evidence is incomplete")
            previous = luma
    clipboard = result.get("clipboard", {})
    if not clipboard.get("expected_utf8") or clipboard.get("copied_utf8") != clipboard.get("expected_utf8") \
            or clipboard.get("sentinel_utf8") == clipboard.get("expected_utf8") \
            or not clipboard.get("sentinel_utf8") or clipboard.get("sentinel_verified") is not True \
            or clipboard.get("probe_helpers_reaped_before_idle") is not True \
            or not all(screenshot_present(directory, clipboard.get(key))
                       for key in ("pasted_screenshot", "restored_fixture_screenshot")):
        errors.append("external clipboard evidence or pre-idle helper cleanup is incomplete")
    fields["desktop_evidence_status"] = "incomplete" if errors else "complete"
    return fields, errors


def control_metadata(outcome, directory):
    fields = dict.fromkeys(CONTROL_FIELDS, "")
    result = outcome.get("control_system_theme")
    errors = []
    if not isinstance(result, dict):
        if outcome.get("measurement_profile") == "diagnostic-reduced":
            fields["control_theme_evidence_status"] = "missing"
            errors.append("reduced control system-theme prerequisite is missing")
        return fields, errors
    fields.update(control_theme_profile=result.get("profile", ""), control_theme_status=result.get("status", ""),
                  control_theme_cleanup_status=result.get("cleanup", {}).get("status", ""))
    sidecar = directory / "control-system-theme.json"
    if not sidecar.is_file() or read_json(sidecar) != result:
        errors.append("control system-theme sidecar is missing or differs from outcome")
    if result.get("schema_version") != 1 or result.get("profile") != "control-system-theme-v1":
        errors.append("unknown control system-theme schema/profile")
    if result.get("status") != "passed" or result.get("requested") != "light" \
            or result.get("observed", {}).get("theme") != "light" \
            or result.get("observed_after", {}).get("theme") != "light" \
            or result.get("cleanup", {}).get("status") != "passed":
        errors.append("reduced control system-theme prerequisite or cleanup failed")
    fields["control_theme_evidence_status"] = "incomplete" if errors else "complete"
    return fields, errors


def row_eligibility(row, errors):
    errors = list(errors)
    if row["status"] != "comparison_passed":
        errors.append(f"outcome status={row['status']}")
    if row["cleanup"] != "clean":
        errors.append(f"process cleanup={row['cleanup'] or 'missing'}")
    if row["intervals"] != 120:
        errors.append("120 complete sample intervals are required")
    profile = row["measurement_profile"]
    if not profile and not row["desktop_profile"] and row["framework"] != "egui_reduced":
        scope = "historical"
    elif profile == "desktop-integrated" and row["framework"] != "egui_reduced":
        scope = "primary"
        if row["desktop_evidence_status"] != "complete":
            errors.append("complete desktop acceptance is required")
    elif profile == "diagnostic-reduced" and row["framework"] == "egui_reduced":
        scope = "control"
        if row["desktop_profile"]:
            errors.append("reduced control must not claim desktop acceptance")
        if row["control_theme_evidence_status"] != "complete":
            errors.append("verified common light system-theme prerequisite is required for the reduced control")
    else:
        scope = "excluded"
        errors.append("profile is not an eligible full desktop candidate or reduced control")
    if scope != "historical":
        if row["phase_status"] != "passed":
            errors.append("measurement phase did not pass")
        if not row["source_commit"]:
            errors.append("source commit is missing")
        if row["comparison_requested"] is not True:
            errors.append("comparison_requested must be true")
        if not finite(row["elapsed_seconds"]) or row["elapsed_seconds"] < 120:
            errors.append("measurement duration is shorter than 120 seconds")
    return ("excluded" if errors else scope), "; ".join(dict.fromkeys(errors))


def measurement_evidence_errors(outcome, directory, phase, data):
    """Recompute current-profile summaries from the retained process samples.

    A passing label and a 120-interval counter are not a measurement archive.
    Historical imports retain their original acceptance policy; new desktop and
    reduced-control results must include the samples that produced each summary.
    """
    if outcome.get("measurement_profile") not in ("desktop-integrated", "diagnostic-reduced"):
        return []
    if not component(phase):
        return ["unsafe measurement phase name"]
    paths = [directory / f"{phase}-samples.json", directory / f"{phase}-samples.json.gz"]
    present = [path for path in paths if path.is_file() and not path.is_symlink()]
    if not present:
        return ["raw measurement samples are missing"]
    try:
        def reject_constant(value):
            raise ValueError(f"Non-finite sample number: {value}")

        samples = []
        for path in present:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8-sig") as stream:
                    rows = json.load(stream, parse_constant=reject_constant)
            else:
                rows = read_json(path)
            samples.append(rows)
        rows = samples[0]
        if any(other != rows for other in samples[1:]):
            raise ValueError("plain and compressed samples differ")
        if not isinstance(rows, list) or len(rows) != 121:
            raise ValueError("121 samples (baseline plus 120 intervals) are required")
        application = outcome.get("desktop_integration", {}).get("application_process", {})
        application_identity = (application.get("pid"), application.get("created")) if application else None
        previous_time, previous_cpu = None, {}
        for row in rows:
            if not isinstance(row, dict) or not finite(row.get("monotonic")) or not finite(row.get("wall_time")):
                raise ValueError("sample timestamps are missing or invalid")
            if previous_time is not None and row["monotonic"] <= previous_time:
                raise ValueError("sample timestamps are not strictly increasing")
            previous_time = row["monotonic"]
            processes = row.get("processes")
            if not isinstance(processes, list) or not processes:
                raise ValueError("sample process scope is missing or empty")
            identities = set()
            for process in processes:
                if not isinstance(process, dict) or type(process.get("pid")) is not int or process["pid"] < 1 \
                        or not finite(process.get("created")) or process["created"] <= 0:
                    raise ValueError("invalid sampled process identity")
                identity = process["pid"], process["created"]
                if identity in identities:
                    raise ValueError("duplicate process identity within a sample")
                identities.add(identity)
                for field in ("rss_bytes", "primary_bytes"):
                    if type(process.get(field)) is not int or process[field] < 0:
                        raise ValueError(f"invalid process {field}")
                cpu = process.get("cpu_seconds")
                if not finite(cpu) or cpu < 0 or cpu < previous_cpu.get(identity, 0):
                    raise ValueError("invalid or decreasing process CPU counter")
                previous_cpu[identity] = cpu
            if application_identity and application_identity not in identities:
                raise ValueError("accepted application process is absent from a resource sample")
            for family_field, process_field in (("family_rss_bytes", "rss_bytes"),
                                                ("family_primary_bytes", "primary_bytes")):
                if type(row.get(family_field)) is not int or row[family_field] != sum(p[process_field] for p in processes):
                    raise ValueError(f"{family_field} differs from the sampled process sum")
        # Reuse the probe's published statistic definitions, not the reported
        # aggregate values. This also verifies idle CPU identity accounting.
        from native_probe import summarize
        recomputed = summarize(rows)
        if recomputed["late_discovered_preexisting_processes"]:
            raise ValueError("pre-existing process was discovered after the CPU baseline")

        def matches(actual, expected):
            if isinstance(expected, dict):
                return isinstance(actual, dict) and all(matches(actual.get(key), value) for key, value in expected.items())
            if isinstance(expected, list):
                return actual == expected
            return finite(actual) and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-7)

        if not matches(data.get("summary"), recomputed):
            raise ValueError("reported summary differs from recomputed raw samples")
    except (OSError, EOFError, ValueError, KeyError, TypeError) as error:
        return [f"raw measurement evidence invalid: {error}"]
    return []


def provenance_errors(outcome, run_id, repetition, source):
    """Normal/dark acceptance must retain, not overwrite, artifact identity."""
    errors = []
    env = outcome.get("environment", {})
    for key, expected in (("run_id", run_id), ("repetition", repetition)):
        actual = env.get(key)
        if actual is not None and str(actual) != str(expected):
            errors.append(f"outcome {key} differs from artifact")
        elif actual is None and outcome.get("measurement_profile"):
            errors.append(f"outcome {key} is missing")
    commit_path = source / "build" / "source-commit.txt"
    if commit_path.is_file() and commit_path.read_text(encoding="utf-8-sig").strip() != env.get("commit"):
        errors.append("outcome source commit differs from recorded build source")
    return errors


def rows_for(run_id: str, runner: str, repetition: int, source: Path):
    sizes_path = source / "build" / "binary-sizes.json"
    sizes = read_json(sizes_path) if sizes_path.exists() else {}
    identity = build_identity(source)
    for fw in FRAMEWORKS:
        path = source / fw / "outcome.json"
        if not path.exists():
            continue
        outcome = read_json(path)
        env = outcome.get("environment", {})
        desktop, desktop_errors = desktop_metadata(outcome, path.parent)
        control, control_errors = control_metadata(outcome, path.parent)
        phases = [(name, data) for name, data in outcome.get("phases", {}).items() if name != "diagnostic"]
        if not phases and (outcome.get("comparison_requested") is True or outcome.get("status") == "comparison_passed"):
            # A failed desktop gate has no samples, but is still a failed requested
            # repetition, not an omitted or successful zero-memory result.
            phases = [("comparison", {})]
        for phase, data in phases:
            summary = data.get("summary", {})
            errors = desktop_errors + control_errors + measurement_evidence_errors(outcome, path.parent, phase, data)

            def number(value, label, digits=3):
                if not finite(value) or value < 0:
                    errors.append(f"missing/invalid {label}")
                    return ""
                return round(value, digits)

            row = dict(os=runner, framework=fw, phase=phase, repetition=repetition,
                       status=outcome.get("status", "missing"), cleanup=outcome.get("cleanup_status", ""), run_id=run_id,
                       source_commit=env.get("commit") or "", image_version=env.get("image_version") or "",
                       primary_metric=outcome.get("primary_memory_metric", ""),
                       primary_median_mib=number(summary.get("family_primary_mib", {}).get("median"), "primary median"),
                       primary_p95_mib=number(summary.get("family_primary_mib", {}).get("p95"), "primary p95"),
                       rss_metric=outcome.get("memory_metric", ""),
                       rss_median_mib=number(summary.get("family_rss_mib", {}).get("median"), "RSS median"),
                       cpu_percent_one_core=number(summary.get("observed_cpu_percent_one_core"), "CPU", 6),
                       elapsed_seconds=number(summary.get("seconds"), "duration"), intervals=summary.get("sample_intervals", ""),
                       executable_bytes=sizes.get(fw, {}).get("executable_bytes", ""),
                       measurement_profile=outcome.get("measurement_profile", ""), **desktop, **control,
                       source_hash=env.get("source_hash") or "", **identity,
                       phase_status=data.get("status", ""), comparison_requested=outcome.get("comparison_requested", ""),
                       reason=outcome.get("reason", ""))
            if not row["primary_metric"] or not row["rss_metric"]:
                errors.append("memory metrics must be named")
            if finite(row["primary_median_mib"]) and finite(row["primary_p95_mib"]) \
                    and row["primary_p95_mib"] < row["primary_median_mib"]:
                errors.append("primary p95 cannot be smaller than the median")
            errors.extend(provenance_errors(outcome, run_id, repetition, source))
            row["eligibility"], row["exclusion_reason"] = row_eligibility(row, errors)
            yield row


def acceptance_rows(run_id, runner, repetition, source):
    identity = build_identity(source)
    for case, base in (("normal", source), ("dark-startup", source / "dark")):
        for fw in FRAMEWORKS:
            path = base / fw / "outcome.json"
            if not path.is_file():
                continue
            outcome = read_json(path)
            env = outcome.get("environment", {})
            desktop, errors = desktop_metadata(outcome, path.parent)
            control, control_errors = control_metadata(outcome, path.parent)
            provenance = provenance_errors(outcome, run_id, repetition, source)
            if provenance:
                # Downstream report builders use this field as a gate; an error
                # string alone must not leave a stale pass eligible for display.
                if desktop["desktop_evidence_status"] == "complete":
                    desktop["desktop_evidence_status"] = "incomplete"
                if control["control_theme_evidence_status"] == "complete":
                    control["control_theme_evidence_status"] = "incomplete"
            yield dict(os=runner, framework=fw, repetition=repetition, case=case, status=outcome.get("status", ""),
                       cleanup_status=outcome.get("cleanup_status", ""),
                       measurement_profile=outcome.get("measurement_profile", ""), **desktop, **control,
                       startup_theme=outcome.get("desktop_integration", {}).get("startup_theme", {}).get("expected", ""),
                       run_id=run_id, source_commit=env.get("commit") or "", source_hash=env.get("source_hash") or "",
                       **identity, image_version=env.get("image_version") or "", evidence_errors="; ".join(errors + control_errors + provenance),
                       reason=outcome.get("reason", ""))


def group_key(row, fields=GROUP_FIELDS):
    return tuple(str(row.get(field, "")) for field in fields)


def aggregate(rows, dark, *, controls=False):
    groups, seen = {}, set()
    for row in rows:
        key = group_key(row)
        unique = key + (str(row["repetition"]),)
        if unique in seen:
            raise ValueError(f"Duplicate measurement for {row['os']} {row['framework']} r{row['repetition']} {row['phase']}")
        seen.add(unique)
        if (row["framework"] == "egui_reduced") == controls:
            groups.setdefault(key, []).append(row)
    out = []
    for _, group in sorted(groups.items()):
        accepted = ("control",) if controls else ("primary", "historical")
        passed = [r for r in group if r["eligibility"] in accepted]
        if not passed:
            continue
        first = passed[0]
        primary = [r["primary_median_mib"] for r in passed]
        rss = [r["rss_median_mib"] for r in passed]
        cpu = [r["cpu_percent_one_core"] for r in passed]
        centre = statistics.median(primary)
        outliers = [r["repetition"] for r in passed
                    if abs(r["primary_median_mib"] - centre) > OUTLIER_FRACTION * centre]
        sizes = [r["executable_bytes"] for r in passed if finite(r["executable_bytes"]) and r["executable_bytes"] >= 0]
        follows_dark = ""
        if first["eligibility"] == "historical":
            # A legacy one-off appearance observation is not desktop acceptance.
            dark_key = (first["os"], first["framework"], first["run_id"], first["source_commit"])
            follows_dark = dark.get(dark_key, dark.get((first["os"], first["framework"]), ""))
        elif first["eligibility"] == "primary":
            follows_dark = True
        out.append(dict(
            os=first["os"], framework=first["framework"], phase=first["phase"], repetitions=len(passed),
            failed_repetitions=len(group) - len(passed), primary_metric=first["primary_metric"],
            primary_median_mib=round(centre, 2), primary_min_mib=round(min(primary), 2), primary_max_mib=round(max(primary), 2),
            primary_spread_percent=round(100 * (max(primary) - min(primary)) / centre, 1) if centre else 0,
            outlier_repetitions=" ".join(map(str, outliers)), rss_metric=first["rss_metric"],
            rss_median_mib=round(statistics.median(rss), 2), rss_min_mib=round(min(rss), 2), rss_max_mib=round(max(rss), 2),
            cpu_median_percent=round(statistics.median(cpu), 5), cpu_max_percent=round(max(cpu), 5),
            executable_bytes=int(statistics.median(sizes)) if sizes else "", follows_dark_mode=follows_dark,
            run_id=first["run_id"], source_commit=first["source_commit"], measurement_profile=first["measurement_profile"],
            desktop_profile=first["desktop_profile"], desktop_status=first["desktop_status"], image_version=first["image_version"],
            **{field: first[field] for field in CONTROL_FIELDS},
            source_hash=first["source_hash"], source_manifest_sha256=first["source_manifest_sha256"],
            build_inputs_sha256=first["build_inputs_sha256"], scope=first["eligibility"]))
    return out


def paired_egui(rows):
    fields = tuple(field for field in GROUP_FIELDS
                   if field not in ("framework", "measurement_profile", "desktop_profile", "control_theme_profile"))
    groups = {}
    for row in rows:
        if row["framework"] in ("egui", "egui_reduced") and row["measurement_profile"]:
            group = groups.setdefault(group_key(row, fields) + (str(row["repetition"]),), {})
            if row["framework"] in group:
                raise ValueError("Multiple measurement profiles for one egui A/B pair identity")
            group[row["framework"]] = row
    pairs, summary_groups = [], {}
    for key, group in sorted(groups.items()):
        desktop, reduced = group.get("egui"), group.get("egui_reduced")
        reference = desktop or reduced
        pair = {field: reference.get(field, "") for field in (*fields, "repetition")}
        pair.update(status="not_paired", desktop=desktop, reduced=reduced)
        if desktop and reduced and desktop["eligibility"] == "primary" and reduced["eligibility"] == "control":
            pair.update(status="paired",
                        primary_delta_mib=round(desktop["primary_median_mib"] - reduced["primary_median_mib"], 3),
                        rss_delta_mib=round(desktop["rss_median_mib"] - reduced["rss_median_mib"], 3),
                        cpu_delta_percentage_points=round(desktop["cpu_percent_one_core"] - reduced["cpu_percent_one_core"], 6),
                        primary_delta_percent=round(100 * (desktop["primary_median_mib"] / reduced["primary_median_mib"] - 1), 2)
                        if reduced["primary_median_mib"] else None)
            if all(finite(row["executable_bytes"]) for row in (desktop, reduced)):
                pair["executable_delta_bytes"] = desktop["executable_bytes"] - reduced["executable_bytes"]
            summary_groups.setdefault(key[:-1], []).append(pair)
        else:
            pair["reason"] = "Missing same-provenance counterpart or one profile is not eligible; no delta computed"
        pairs.append(pair)
    summaries = []
    for group in summary_groups.values():
        row = {field: group[0][field] for field in fields}
        row.update(paired_repetitions=len(group),
                   primary_delta_median_mib=round(statistics.median(p["primary_delta_mib"] for p in group), 3),
                   primary_delta_min_mib=min(p["primary_delta_mib"] for p in group),
                   primary_delta_max_mib=max(p["primary_delta_mib"] for p in group),
                   rss_delta_median_mib=round(statistics.median(p["rss_delta_mib"] for p in group), 3),
                   cpu_delta_median_percentage_points=round(statistics.median(p["cpu_delta_percentage_points"] for p in group), 6))
        summaries.append(row)
    return dict(schema_version=1, delta_definition="desktop-integrated minus diagnostic-reduced, paired within one runner/repetition",
                pairs=pairs, summary=summaries, limitations=[
                    "This measures the configured profile difference, not clipboard-only or theme-only allocation",
                    "The desktop profile was exercised through real OS clipboard and appearance changes; the reduced control cannot pass that workload",
                    "The reduced control is diagnostic only and is excluded from the primary desktop comparison",
                    "Shared OS services outside the application's process scope are not attributed; GPU/VRAM allocations are not comprehensively measured",
                    "Small paired samples and sequential execution do not establish statistical significance"])


def write_csv(path: Path, rows, fieldnames=None):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames or list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    run_id, base, series = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    if not run_id.isdecimal() or not component(series):
        print("RUN_ID must be numeric and SERIES_NAME must be one safe path component", file=sys.stderr)
        return 2
    artifacts = list(artifact_dirs(base, run_id))
    if not artifacts:
        print("No artifacts found", file=sys.stderr)
        return 1
    rows, dark, acceptance = [], {}, []
    for runner, repetition, source in artifacts:
        target = ROOT / "measurements" / f"native-{run_id}" / f"r{repetition}" / runner
        shots = ROOT / "screenshots" / f"native-{run_id}" / runner
        copy_evidence(source, target, repetition, runner, shots)
        rows.extend(rows_for(run_id, runner, repetition, source))
        acceptance.extend(acceptance_rows(run_id, runner, repetition, source))
        summary_path = source / "dark" / "appearance-summary.json"
        if repetition == 1 and summary_path.exists():
            for fw, entry in read_json(summary_path).items():
                light_path = source / fw / "outcome.json"
                if light_path.exists():
                    light = read_json(light_path)
                    if not light.get("measurement_profile"):
                        dark[(runner, fw, run_id, light.get("environment", {}).get("commit") or "")] = entry.get("follows_dark_mode", "")
    rows.sort(key=lambda r: (r["os"], FRAMEWORKS.index(r["framework"]), r["phase"], group_key(r), r["repetition"]))
    summary, controls = aggregate(rows, dark), aggregate(rows, {}, controls=True)
    out = ROOT / "measurements" / series
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "runs.csv", rows, RUN_FIELDS)
    write_csv(out / "summary.csv", summary, SUMMARY_FIELDS)
    write_csv(out / "controls.csv", controls, SUMMARY_FIELDS)
    write_csv(out / "desktop-acceptance.csv", acceptance, ACCEPTANCE_FIELDS)
    write_json(out / "paired-egui-ab.json", paired_egui(rows))
    write_json(out / "import-report.json", dict(
        schema_version=1, status="imported" if summary else "no_eligible_primary_rows",
        artifact_count=len(artifacts), outcome_count=len(acceptance), requested_or_measured_phase_rows=len(rows),
        primary_summary_groups=len(summary), control_summary_groups=len(controls),
        exclusions=[{key: row[key] for key in ("os", "framework", "phase", "repetition", "source_commit", "measurement_profile", "exclusion_reason")}
                    for row in rows if row["eligibility"] == "excluded"]))
    names = ("runs.csv", "summary.csv", "controls.csv", "desktop-acceptance.csv", "paired-egui-ab.json", "import-report.json")
    (out / "SHA256SUMS").write_text("\n".join(f"{digest(out / name)}  {name}" for name in names) + "\n", encoding="utf-8")
    for row in summary:
        flag = f" outliers r{row['outlier_repetitions']}" if row["outlier_repetitions"] else ""
        print(f"{row['os']:13} {row['framework']:6} {row['phase']:10} n={row['repetitions']} "
              f"primary {row['primary_median_mib']:8.2f} [{row['primary_min_mib']}–{row['primary_max_mib']}] "
              f"spread {row['primary_spread_percent']}%{flag} profile={row['measurement_profile'] or 'historical-unspecified'}")
    if not summary:
        print("Evidence imported, but no eligible primary comparison rows; inspect import-report.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
