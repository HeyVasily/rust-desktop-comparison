#!/usr/bin/env python3
"""Build optional site data from a real imported series, without inventing results.

Usage: python3 tools/build_desktop_site_data.py measurements/SERIES [--output PATH] [--check]
Default output: data/desktop-results.json. Schema: site/desktop-data-schema.md.
CSV values are preserved as strings; only presentation/evidence grouping is added.
The importer remains responsible for checking raw captures and measurement scope.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/HeyVasily/rust-desktop-comparison"
FRAMEWORKS = {"egui": "egui / eframe", "gtk": "GTK4 + libadwaita", "slint": "Slint",
              "qt": "Qt Widgets", "tauri": "Tauri"}
PLATFORMS = {"linux": "Linux", "windows": "Windows", "macos": "macOS"}
IDENTITY = ("os", "run_id", "source_commit", "source_hash", "source_manifest_sha256",
            "build_inputs_sha256", "image_version")
CHECKS = {"live_theme": "live_theme_status", "clipboard": "clipboard_status",
          "cleanup": "desktop_cleanup_status", "process_cleanup": "cleanup_status",
          "evidence": "desktop_evidence_status"}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def platform(runner):
    for prefix, value in (("ubuntu-", "linux"), ("debian-", "linux"), ("linux-", "linux"),
                          ("windows-", "windows"), ("macos-", "macos")):
        if runner.startswith(prefix):
            return value
    raise ValueError(f"Unknown runner OS: {runner}")


def number(value, *, integer=False, nonnegative=True):
    if value in (None, "") or isinstance(value, bool):
        raise ValueError("Missing numeric evidence")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0) or (integer and result != int(result)):
        raise ValueError(f"Invalid numeric evidence: {value}")
    return result


def identity(row):
    return tuple(str(row.get(field, "")) for field in IDENTITY)


def repo_file(path, root):
    return f"{REPO}/blob/main/{path.relative_to(root).as_posix()}"


def invocation_links(row, root):
    run, rep, runner, framework = (str(row.get(key, "")) for key in ("run_id", "repetition", "os", "framework"))
    if not run.isdecimal() or not rep.isdecimal() or int(rep) < 1 or not re.fullmatch(r"[A-Za-z0-9._-]+", runner):
        raise ValueError("Unsafe or missing artifact identity")
    directory = root / "measurements" / f"native-{run}" / f"r{rep}" / runner
    if row["case"] == "dark-startup":
        directory /= "dark"
    elif row["case"] != "normal":
        raise ValueError(f"Unknown acceptance case: {row['case']}")
    directory /= framework
    links = {name: repo_file(directory / filename, root)
             for name, filename in (("outcome", "outcome.json"), ("desktop", "desktop-integration.json"))
             if (directory / filename).is_file()}
    links["screenshots"] = [{"label": path.stem, "url": repo_file(path, root)}
                            for path in sorted(directory.glob("*.png")) if path.is_file() and not path.is_symlink()]
    return links


def check_status(rows, field, *, success="passed"):
    if not rows:
        return "not_run"
    values = [row.get(field, "") for row in rows]
    if "environment_error" in values:
        return "environment_error"
    if "failed" in values:
        return "failed"
    return "passed" if all(value == success for value in values) else "incomplete"


def acceptance(rows, provenance):
    light = [row for row in rows if row["case"] == "normal" and row["startup_theme"] == "light"]
    dark = [row for row in rows if row["case"] == "dark-startup" and row["startup_theme"] == "dark"]
    result = dict(startup_light=check_status(light, "startup_theme_status"),
                  startup_dark=check_status(dark, "startup_theme_status"),
                  **{label: check_status(rows, field, success={"evidence": "complete", "process_cleanup": "clean"}.get(label, "passed"))
                     for label, field in CHECKS.items()},
                  normal_invocations=sum(row["case"] == "normal" for row in rows),
                  dark_invocations=sum(row["case"] == "dark-startup" for row in rows))
    # Failed setup can have no startup expectation; retain that failure separately.
    environment_error = any(row.get("desktop_status") == "environment_error" for row in rows) \
        or "environment_error" in result.values()
    failed = any(row.get("desktop_status") == "failed" or row.get("status") == "failed" for row in rows)
    qualified = bool(rows) and all(
        row.get("measurement_profile") == "desktop-integrated"
        and row.get("desktop_profile") == "desktop-acceptance-v1"
        and row.get("desktop_status") == "passed"
        and row.get("status") in ("comparison_passed", "diagnostic_passed")
        and row["links"].get("outcome") and row["links"].get("desktop") and row["links"]["screenshots"]
        for row in rows)
    provenance_complete = bool(re.fullmatch(r"[0-9a-fA-F]{40,64}", provenance.get("source_commit", ""))) \
        and str(provenance.get("run_id", "")).isdecimal() and bool(provenance.get("image_version", "").strip()) \
        and all(re.fullmatch(r"[0-9a-fA-F]{64}", provenance.get(key, ""))
                for key in ("source_manifest_sha256", "build_inputs_sha256"))
    result["provenance"] = "passed" if provenance_complete else "incomplete" if rows else "not_run"
    result["status"] = ("fully_verified" if provenance_complete and qualified and all(result[key] == "passed"
                         for key in ("startup_light", "startup_dark", *CHECKS)) else
                         "environment_error" if environment_error else "failed" if failed else "incomplete" if rows else "not_run")
    return result


def build(series, *, root=ROOT):
    root, series = Path(root).resolve(), Path(series).resolve()
    relative = series.relative_to(root)
    if relative.parts[0] != "measurements":
        raise ValueError("The series must be under the repository's measurements directory")
    summaries = read_csv(series / "summary.csv")
    invocations = read_csv(series / "desktop-acceptance.csv")
    def invalid_constant(value):
        raise ValueError(f"Non-finite paired evidence: {value}")
    paired = json.loads((series / "paired-egui-ab.json").read_text(encoding="utf-8"), parse_constant=invalid_constant)
    if paired.get("schema_version") != 1:
        raise ValueError("Unsupported paired-egui-ab schema")
    groups = {}

    def group(row):
        key = row["framework"], identity(row)
        platform(row["os"])
        if key not in groups:
            ident = dict(zip(IDENTITY, key[1]))
            links = {}
            if str(row.get("run_id", "")).isdecimal():
                links["run"] = f"{REPO}/actions/runs/{row['run_id']}"
            if re.fullmatch(r"[0-9a-fA-F]{40,64}", row.get("source_commit", "")):
                links["commit"] = f"{REPO}/commit/{row['source_commit']}"
            groups[key] = dict(identity=ident, measurements=[], invocations=[], links=links)
        return groups[key]

    for row in invocations:
        if row["framework"] not in FRAMEWORKS:
            continue  # Reduced controls are never primary candidates.
        if row.get("measurement_profile") != "desktop-integrated":
            continue  # Historical rows cannot become current acceptance.
        entry = dict(row, links=invocation_links(row, root))
        group(row)["invocations"].append(entry)
    for row in summaries:
        if row["framework"] not in FRAMEWORKS or row.get("phase") != "comparison" \
                or row.get("measurement_profile") != "desktop-integrated" or row.get("scope") != "primary":
            continue
        for field in ("primary_median_mib", "primary_min_mib", "primary_max_mib", "cpu_median_percent"):
            number(row.get(field))
        if not number(row["primary_min_mib"]) <= number(row["primary_median_mib"]) <= number(row["primary_max_mib"]):
            raise ValueError("Primary median is outside the reported range")
        if number(row.get("repetitions"), integer=True) < 1 or not row.get("primary_metric", "").strip():
            raise ValueError("Primary summary lacks repetitions or metric")
        entry = group(row)
        if any(old["primary_metric"] == row["primary_metric"] for old in entry["measurements"]):
            raise ValueError("Duplicate primary summary for the same provenance and metric")
        entry["measurements"].append(dict(row))
    platforms = []
    for os_id, label in PLATFORMS.items():
        candidates = []
        for framework, name in FRAMEWORKS.items():
            experiments = [value for (fw, ident), value in sorted(groups.items())
                           if fw == framework and platform(ident[0]) == os_id]
            for experiment in experiments:
                experiment["acceptance"] = acceptance(experiment["invocations"], experiment["identity"])
            candidates.append(dict(framework=framework, name=name, experiments=experiments))
        platforms.append(dict(id=os_id, name=label, candidates=candidates))
    ab = []
    for row in paired.get("summary", []):
        if row.get("phase") != "comparison":
            continue
        os_id = platform(row["os"])
        if number(row.get("paired_repetitions"), integer=True) < 1 or not row.get("primary_metric", "").strip():
            raise ValueError("Paired summary lacks pairs or a named metric")
        for field in ("primary_delta_median_mib", "primary_delta_min_mib", "primary_delta_max_mib"):
            number(row.get(field), nonnegative=False)
        if not number(row["primary_delta_min_mib"], nonnegative=False) <= number(row["primary_delta_median_mib"], nonnegative=False) <= number(row["primary_delta_max_mib"], nonnegative=False):
            raise ValueError("Paired median is outside the reported range")
        ab.append(dict(row, platform=os_id, source_url=repo_file(series / "paired-egui-ab.json", root)))
    return dict(schema_version=1, series=relative.as_posix(), platforms=platforms, paired_ab=ab,
                sources=[dict(label=name, url=repo_file(series / name, root)) for name in
                         ("summary.csv", "desktop-acceptance.csv", "paired-egui-ab.json")],
                limitations=[
                    "Memory n counts measured comparison invocations; startup/clipboard acceptance invocations are listed separately.",
                    "Fully verified requires light startup, separate dark startup, live transitions, clipboard and complete evidence from the same source/build identity.",
                    "Linux CI is X11/Xvfb with Mesa llvmpipe, not native Wayland or hardware-GPU acceptance.",
                    "Linux PSS, Windows private working set and macOS physical footprint are not interchangeable across operating systems.",
                    "Paired egui deltas measure the configured desktop profile after use minus the reduced diagnostic control, not clipboard-only allocation."])


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("series", type=Path)
    parser.add_argument("--output", type=Path, default=Path(root) / "data/desktop-results.json")
    parser.add_argument("--check", action="store_true", help="Check the published JSON without modifying it")
    args = parser.parse_args(argv)
    data = build(args.series, root=root)
    rendered = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered:
            print(f"Stale or missing {args.output}; regenerate it from {args.series}")
            return 1
        print(f"Verified {args.output} against {args.series}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} from {args.series}; no historical data was changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
