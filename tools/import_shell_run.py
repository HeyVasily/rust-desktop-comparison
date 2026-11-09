#!/usr/bin/env python3
"""Import a shell-integration run into the repository and tabulate the verdicts.

Usage: import_shell_run.py RUN_ID ARTIFACT_DIR

ARTIFACT_DIR holds `gh run download RUN_ID` output (one shell-<runner>-<run-id>
directory per OS). Writes measurements/shell-<run-id>/<runner>/<framework>/ with the
probe result and application logs, screenshots/shell-<run-id>/<runner>/<framework>.png,
and measurements/shell-<run-id>/summary.csv with one row per OS, framework and check.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get("IMPORT_ROOT", Path(__file__).resolve().parent.parent))
FRAMEWORKS = ("egui", "gtk", "slint", "qt", "tauri")
CHECKS = ("tray", "badge", "attention", "hotkey", "single_instance")
BUILD_FILES = ("native-versions.txt", "gtk-version.txt", "gtk-rust-version.txt", "openbox.log")


def detail(check: str, data: dict) -> str:
    app = data.get("app") or {}
    parts = [f"app: {app.get('status', 'no report')} ({app.get('detail', '')})"]
    if "how" in data:
        parts.append(data["how"])
    if check == "tray" and "clicked" in data:
        parts.append("click " + ("received" if data["clicked"] else "not received"))
    if check == "single_instance":
        parts.append("second launch " + ("exited" if data.get("second_exited") else "kept running"))
        parts.append("forwarded to first" if data.get("forwarded") else "not forwarded")
    if check == "hotkey" and "injected" in data:
        parts.append(data["injected"])
    return "; ".join(p for p in parts if p)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    run_id, base = sys.argv[1], Path(sys.argv[2])
    pattern = re.compile(rf"shell-(?P<runner>.+)-{run_id}$")
    rows = []
    out = ROOT / "measurements" / f"shell-{run_id}"
    for artifact in sorted(base.iterdir()):
        match = pattern.match(artifact.name)
        if not (artifact.is_dir() and match):
            continue
        runner = match["runner"]
        target = out / runner
        (target / "build").mkdir(parents=True, exist_ok=True)
        for name in BUILD_FILES:
            if (artifact / "build" / name).exists():
                shutil.copy2(artifact / "build" / name, target / "build" / name)
        for name in ("sni-watcher.log", "launcher-entry.log"):
            if (artifact / name).exists():
                shutil.copy2(artifact / name, target / name)
        for fw in FRAMEWORKS:
            source = artifact / "shell" / fw
            result_path = source / "result.json"
            if not result_path.exists():
                rows.append(dict(os=runner, framework=fw, check="all", verdict="not-run",
                                 detail="no result; see the build log", run_id=run_id))
                continue
            (target / fw).mkdir(parents=True, exist_ok=True)
            for item in ("result.json", "application.log", "second-instance.log"):
                if (source / item).exists():
                    shutil.copy2(source / item, target / fw / item)
            if (source / "running.png").exists():
                shots = ROOT / "screenshots" / f"shell-{run_id}" / runner
                shots.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / "running.png", shots / f"{fw}.png")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            for check in CHECKS:
                data = result.get("checks", {}).get(check)
                if data is None:
                    rows.append(dict(os=runner, framework=fw, check=check, verdict="not-run",
                                     detail=result.get("error", "probe stopped before this check"), run_id=run_id))
                    continue
                rows.append(dict(os=runner, framework=fw, check=check, verdict=data.get("verdict", "fail"),
                                 detail=detail(check, data), run_id=run_id))
    if not rows:
        print("No shell artifacts found", file=sys.stderr)
        return 1
    rows.sort(key=lambda r: (r["os"], FRAMEWORKS.index(r["framework"]), r["check"]))
    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['os']:13} {row['framework']:6} {row['check']:16} {row['verdict']:9} {row['detail'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
