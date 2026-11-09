#!/usr/bin/env python3
"""Import downloaded native-comparison artifacts into the repository and aggregate them.

Usage: import_native_run.py RUN_ID ARTIFACT_DIR SERIES_NAME

ARTIFACT_DIR holds `gh run download RUN_ID` output: one directory per artifact,
named native-<runner>-<run-id>[-r<repetition>]. The script writes

  measurements/native-<run-id>/r<k>/<runner>/...   outcomes, gzipped samples, logs
  screenshots/native-<run-id>/<runner>/<fw>.png    repetition 1 light capture
  screenshots/native-<run-id>/<runner>/<fw>-dark.png  repetition 1 dark capture
  measurements/<series>/runs.csv                   one row per repetition and phase
  measurements/<series>/summary.csv                median of repetition medians, spread, outliers
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import statistics
import sys
from pathlib import Path

ROOT = Path(os.environ.get("IMPORT_ROOT", Path(__file__).resolve().parent.parent))
FRAMEWORKS = ("egui", "gtk", "slint", "qt", "tauri")
OUTLIER_FRACTION = 0.10
BUILD_FILES = ("binary-sizes.json", "native-versions.txt", "gtk-version.txt", "gtk-rust-version.txt",
               "rust-version.txt", "cmake-version.txt", "webview2-version.txt", "glxinfo.txt",
               "probe-python.txt", "windows-gtk-runtime.json")
DARK_FILES = ("appearance-summary.json", "system-setting.txt", "gsettings.txt", "osascript.log")


def artifact_dirs(base: Path, run_id: str):
    pattern = re.compile(rf"native-(?P<runner>.+?)-{run_id}(?:-r(?P<rep>\d+))?$")
    for path in sorted(base.iterdir()):
        match = pattern.match(path.name)
        if path.is_dir() and match:
            yield match["runner"], int(match["rep"] or 1), path


def copy_evidence(source: Path, target: Path, repetition: int, runner: str, shots: Path):
    target.mkdir(parents=True, exist_ok=True)
    for name in BUILD_FILES:
        if (source / "build" / name).exists():
            (target / "build").mkdir(exist_ok=True)
            shutil.copy2(source / "build" / name, target / "build" / name)
    for fw in FRAMEWORKS:
        src = source / fw
        if not src.is_dir():
            continue
        dst = target / fw
        dst.mkdir(exist_ok=True)
        for item in src.iterdir():
            if item.name.endswith("-samples.json"):
                # mtime=0 keeps the gzip bytes reproducible for SHA256 checks.
                with item.open("rb") as raw, (dst / (item.name + ".gz")).open("wb") as file, \
                        gzip.GzipFile(fileobj=file, mode="wb", mtime=0, filename="") as packed:
                    shutil.copyfileobj(raw, packed)
            elif item.suffix in (".json", ".log"):
                shutil.copy2(item, dst / item.name)
        if repetition == 1 and (src / "comparison.png").exists():
            shots.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / "comparison.png", shots / f"{fw}.png")
    dark = source / "dark"
    if repetition == 1 and dark.is_dir():
        (target / "dark").mkdir(exist_ok=True)
        for name in DARK_FILES:
            if (dark / name).exists():
                shutil.copy2(dark / name, target / "dark" / name)
        for fw in FRAMEWORKS:
            if (dark / fw / "diagnostic.png").exists():
                shutil.copy2(dark / fw / "diagnostic.png", shots / f"{fw}-dark.png")
            if (dark / fw / "outcome.json").exists():
                (target / "dark" / fw).mkdir(parents=True, exist_ok=True)
                shutil.copy2(dark / fw / "outcome.json", target / "dark" / fw / "outcome.json")


def rows_for(run_id: str, runner: str, repetition: int, source: Path):
    sizes = {}
    if (source / "build" / "binary-sizes.json").exists():
        sizes = json.loads((source / "build" / "binary-sizes.json").read_text())
    for fw in FRAMEWORKS:
        path = source / fw / "outcome.json"
        if not path.exists():
            continue
        outcome = json.loads(path.read_text())
        env = outcome.get("environment", {})
        for phase, data in outcome.get("phases", {}).items():
            if phase == "diagnostic":
                continue
            summary = data["summary"]
            yield dict(
                os=runner, framework=fw, phase=phase, repetition=repetition, status=outcome["status"],
                cleanup=outcome.get("cleanup_status"), run_id=run_id,
                source_commit=env.get("commit"), image_version=env.get("image_version"),
                primary_metric=outcome.get("primary_memory_metric"),
                primary_median_mib=round(summary["family_primary_mib"]["median"], 3),
                primary_p95_mib=round(summary["family_primary_mib"]["p95"], 3),
                rss_metric=outcome.get("memory_metric"),
                rss_median_mib=round(summary["family_rss_mib"]["median"], 3),
                cpu_percent_one_core=round(summary["observed_cpu_percent_one_core"], 6),
                elapsed_seconds=round(summary["seconds"], 3), intervals=summary["sample_intervals"],
                executable_bytes=sizes.get(fw, {}).get("executable_bytes", ""),
            )


def aggregate(rows, dark):
    groups = {}
    for row in rows:
        groups.setdefault((row["os"], row["framework"], row["phase"]), []).append(row)
    out = []
    for (runner, fw, phase), group in sorted(groups.items()):
        passed = [r for r in group if r["status"] == "comparison_passed" and r["cleanup"] == "clean"
                  and r["intervals"] == 120]
        if not passed:
            continue
        primary = [r["primary_median_mib"] for r in passed]
        rss = [r["rss_median_mib"] for r in passed]
        cpu = [r["cpu_percent_one_core"] for r in passed]
        centre = statistics.median(primary)
        outliers = [r["repetition"] for r in passed
                    if abs(r["primary_median_mib"] - centre) > OUTLIER_FRACTION * centre]
        sizes = [r["executable_bytes"] for r in passed if r["executable_bytes"] != ""]
        out.append(dict(
            os=runner, framework=fw, phase=phase, repetitions=len(passed),
            failed_repetitions=len(group) - len(passed),
            primary_metric=passed[0]["primary_metric"],
            primary_median_mib=round(centre, 2), primary_min_mib=round(min(primary), 2),
            primary_max_mib=round(max(primary), 2),
            primary_spread_percent=round(100 * (max(primary) - min(primary)) / centre, 1),
            outlier_repetitions=" ".join(map(str, outliers)),
            rss_metric=passed[0]["rss_metric"], rss_median_mib=round(statistics.median(rss), 2),
            rss_min_mib=round(min(rss), 2), rss_max_mib=round(max(rss), 2),
            cpu_median_percent=round(statistics.median(cpu), 5), cpu_max_percent=round(max(cpu), 5),
            executable_bytes=int(statistics.median(sizes)) if sizes else "",
            follows_dark_mode=dark.get((runner, fw), ""),
            run_id=passed[0]["run_id"], source_commit=passed[0]["source_commit"],
        ))
    return out


def write_csv(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    run_id, base, series = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    rows, dark = [], {}
    for runner, repetition, source in artifact_dirs(base, run_id):
        target = ROOT / "measurements" / f"native-{run_id}" / f"r{repetition}" / runner
        shots = ROOT / "screenshots" / f"native-{run_id}" / runner
        copy_evidence(source, target, repetition, runner, shots)
        rows.extend(rows_for(run_id, runner, repetition, source))
        summary = source / "dark" / "appearance-summary.json"
        if repetition == 1 and summary.exists():
            for fw, entry in json.loads(summary.read_text()).items():
                dark[(runner, fw)] = entry.get("follows_dark_mode", "")
    if not rows:
        print("No artifacts found", file=sys.stderr)
        return 1
    out = ROOT / "measurements" / series
    out.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (r["os"], FRAMEWORKS.index(r["framework"]), r["phase"], r["repetition"]))
    write_csv(out / "runs.csv", rows)
    summary = aggregate(rows, dark)
    summary.sort(key=lambda r: (r["os"], FRAMEWORKS.index(r["framework"]), r["phase"]))
    write_csv(out / "summary.csv", summary)
    sums = [f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}" for n in ("runs.csv", "summary.csv")]
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    for row in summary:
        flag = f" outliers r{row['outlier_repetitions']}" if row["outlier_repetitions"] else ""
        print(f"{row['os']:13} {row['framework']:6} {row['phase']:10} n={row['repetitions']} "
              f"primary {row['primary_median_mib']:8.2f} [{row['primary_min_mib']}–{row['primary_max_mib']}] "
              f"spread {row['primary_spread_percent']}%{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
