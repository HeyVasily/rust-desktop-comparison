#!/usr/bin/env python3
"""Run accepted desktop profiles sequentially, preserving failure evidence.

For disposable CI desktops only. The desktop driver changes system appearance
and replaces the clipboard with synthetic text. The reduced egui control is not
a desktop candidate and is never allowed into the primary ranking.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import psutil


NAMES = ("egui", "gtk", "slint", "qt", "tauri")


def selected_candidates(selected, target, *, windows=False, reduced=False, repetition=1):
    if not selected or selected != [name for name in NAMES if name in selected]:
        raise ValueError(f"Invalid selected frameworks: {selected}")
    extension = ".exe" if windows else ""
    candidates = [
        ("egui", "Veranda egui comparison", target / "release" / ("veranda-egui-comparison" + extension)),
        ("gtk", "Veranda GTK comparison", (Path("target/msys2") if windows else target) / "release" / ("veranda-gtk-comparison" + extension)),
        ("slint", "Veranda Slint comparison", target / "release" / ("veranda-slint-comparison" + extension)),
        ("qt", "Veranda Qt Widgets comparison", target / "qt" / ("Release" if windows else "") / ("veranda-qt-comparison" + extension)),
        ("tauri", "Veranda Tauri comparison", target / "release" / ("veranda-tauri-comparison" + extension)),
    ]
    candidates = [candidate for candidate in candidates if candidate[0] in selected]
    if reduced and "egui" in selected:
        control = ("egui_reduced", "Veranda egui comparison", target / "release" / ("veranda-egui-reduced-comparison" + extension))
        # Same runner/repetition, alternate A/B ordering to expose order bias.
        candidates.insert(0 if repetition % 2 else 1, control)
    return candidates


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def record_sizes(candidates, output):
    sizes = {}
    for name, _, executable in candidates:
        if executable.is_file():
            entry = dict(executable=str(executable), executable_bytes=executable.stat().st_size,
                         sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
            if sys.platform == "win32" and name == "qt":
                entry["deployed_directory_bytes"] = sum(p.stat().st_size for p in executable.parent.rglob("*") if p.is_file())
            sizes[name] = entry
    write_json(output / "build" / "binary-sizes.json", sizes)


def verify(output, candidates, comparison, desktop_checks):
    failures = json.loads((output / "failed-candidates.json").read_text())
    assert not failures, f"Incomplete candidates: {failures}; inspect outcomes and captures"
    names = [name for name, _, _ in candidates]
    assert json.loads((output / "selected-candidates.json").read_text()) == names
    assert len(list(output.glob("*/outcome.json"))) == len(names), "Outcome count differs from selection"
    for name in names:
        outcome = json.loads((output / name / "outcome.json").read_text())
        expected = "comparison_passed" if comparison else "diagnostic_passed"
        assert outcome["status"] == expected, f"{name}: {outcome}"
        assert outcome["cleanup_status"] == "clean", f"{name}: process cleanup unverified"
        if name == "egui_reduced":
            assert outcome["measurement_profile"] == "diagnostic-reduced"
        elif desktop_checks:
            desktop = outcome.get("desktop_integration", {})
            assert outcome["measurement_profile"] == "desktop-integrated"
            assert desktop.get("status") == "passed", f"{name}: desktop acceptance missing/failed"
            for check in ("startup_theme", "live_theme", "clipboard"):
                assert desktop.get(check, {}).get("status") == "passed", f"{name}: {check} evidence missing/failed"
            assert desktop.get("cleanup", {}).get("status") == "passed", f"{name}: desktop cleanup failed"
        if comparison:
            assert outcome["phases"]["comparison"]["summary"]["sample_intervals"] == 120


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    parser.add_argument("--startup-theme", choices=("light", "dark"), default="light")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    comparison = os.environ.get("COMPARISON") == "true"
    desktop_checks = os.environ.get("DESKTOP_CHECKS", "true") == "true"
    reduced = os.environ.get("REDUCED_CONTROL", "true") == "true" and args.startup_theme == "light"
    candidates = selected_candidates(json.loads(os.environ["SELECTED_FRAMEWORKS"]),
                                     Path(os.environ["CARGO_TARGET_DIR"]), windows=sys.platform == "win32",
                                     reduced=reduced, repetition=int(os.environ.get("REPETITION", "1")))
    if args.verify_only:
        verify(args.output, candidates, comparison, desktop_checks)
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "selected-candidates.json", [name for name, _, _ in candidates])
    if args.startup_theme == "light":
        (args.output / "build").mkdir(exist_ok=True)
        record_sizes(candidates, args.output)
    failed = []
    for name, title, executable in candidates:
        command = [sys.executable, "tools/native_probe.py", "--name", name, "--title", title,
                   "--executable", str(executable), "--output", str(args.output / name)]
        if sys.platform != "darwin":
            command += ["--client-size", "960", "640"]
        if comparison:
            command += ["--comparison"]
        if desktop_checks and name != "egui_reduced":
            command += ["--desktop-checks", "--startup-theme", args.startup_theme]
        print("Running", name, "with", " ".join(command), flush=True)
        probe = subprocess.Popen(command)
        try:
            if probe.wait(timeout=540):
                failed.append(name)
            try:
                outcome = json.loads((args.output / name / "outcome.json").read_text())
            except (OSError, ValueError):
                outcome = {}
            if (outcome.get("cleanup_status") not in ("clean", "not_needed")
                    or outcome.get("cleanup_survivors") or outcome.get("process_access_denied_pids")
                    or outcome.get("desktop_integration", {}).get("cleanup", {}).get("status") == "failed"):
                if name not in failed:
                    failed.append(name)
                write_json(args.output / "stopped-after.json", dict(
                    name=name, reason="Process/desktop cleanup failed, unknown or missing; later candidates refused"))
                break
        except subprocess.TimeoutExpired:
            family = psutil.Process(probe.pid).children(recursive=True)
            for process in reversed(family):
                try:
                    process.terminate()
                except psutil.NoSuchProcess:
                    pass
            probe.terminate()
            _, alive = psutil.wait_procs(family, timeout=3)
            for process in alive:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            try:
                probe.wait(timeout=5)
            except subprocess.TimeoutExpired:
                probe.kill()
                probe.wait(timeout=5)
            failed.append(name)
            (args.output / name).mkdir(exist_ok=True)
            write_json(args.output / name / "watchdog.json", dict(
                name=name, status="failed", cleanup_status="unknown",
                reason="Probe exceeded 540s watchdog; subsequent candidates refused to avoid contamination"))
            break
    write_json(args.output / "failed-candidates.json", failed)
    # The workflow uploads all evidence before running the strict verification gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
