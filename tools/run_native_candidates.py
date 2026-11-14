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

from desktop_probe import SystemTheme


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


class ControlTheme:
    """Normalize only the reduced control's OS setting; not desktop acceptance."""

    def __init__(self, output, theme=None):
        self.output = output
        self.theme = theme if theme is not None else SystemTheme()
        self.snapshot_complete = False
        self.result = dict(schema_version=1, profile="control-system-theme-v1",
                           status="not_run", requested="light", cleanup={"status": "not_run"},
                           limitation="OS preference prerequisite only; no application theme, live-change or clipboard acceptance is claimed")

    def save(self):
        self.output.mkdir(parents=True, exist_ok=True)
        write_json(self.output / "control-system-theme.json", self.result)

    def prepare(self):
        try:
            self.theme.snapshot()
            self.snapshot_complete = True
            self.result["observed"] = self.theme.set("light")
            if self.result["observed"].get("theme") != "light":
                raise RuntimeError("Reduced control OS preference was not verified light")
            self.result["status"] = "passed"
        except Exception as error:
            self.result.update(status="environment_error", reason=f"{type(error).__name__}: {error}")
            raise
        finally:
            self.save()

    def close(self):
        if self.result["status"] == "passed":
            try:
                self.result["observed_after"] = self.theme.read()
                if self.result["observed_after"].get("theme") != "light":
                    raise RuntimeError("OS preference changed while measuring the reduced control")
            except Exception as error:
                self.result.update(status="environment_error", reason=f"{type(error).__name__}: {error}")
        if self.snapshot_complete:
            try:
                self.theme.restore()
                self.result["cleanup"] = dict(status="passed")
            except Exception as error:
                reason = f"{type(error).__name__}: {error}"
                self.result["cleanup"] = dict(status="failed", reason=reason)
                self.result.update(status="environment_error", reason=f"OS preference restoration failed: {reason}")
        else:
            # No preference mutation is attempted until snapshot succeeds.
            self.result["cleanup"] = dict(status="not_needed")
        self.save()
        return self.result["status"] == "passed" and self.result["cleanup"]["status"] == "passed"


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
    failures = json.loads((output / "failed-candidates.json").read_text(encoding="utf-8"))
    assert not failures, f"Incomplete candidates: {failures}; inspect outcomes and captures"
    names = [name for name, _, _ in candidates]
    assert json.loads((output / "selected-candidates.json").read_text(encoding="utf-8")) == names
    assert len(list(output.glob("*/outcome.json"))) == len(names), "Outcome count differs from selection"
    for name in names:
        outcome = json.loads((output / name / "outcome.json").read_text(encoding="utf-8"))
        expected = "comparison_passed" if comparison else "diagnostic_passed"
        assert outcome["status"] == expected, f"{name}: {outcome}"
        assert outcome["cleanup_status"] == "clean", f"{name}: process cleanup unverified"
        if name == "egui_reduced":
            assert outcome["measurement_profile"] == "diagnostic-reduced"
            control = outcome.get("control_system_theme", {})
            assert control.get("profile") == "control-system-theme-v1"
            assert control.get("schema_version") == 1
            assert control.get("status") == "passed", "Reduced control OS preference unverified"
            assert control.get("requested") == "light"
            assert control.get("observed", {}).get("theme") == "light"
            assert control.get("observed_after", {}).get("theme") == "light"
            assert control.get("cleanup", {}).get("status") == "passed"
            assert json.loads((output / name / "control-system-theme.json").read_text(encoding="utf-8")) == control
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
        control = ControlTheme(args.output / name) if name == "egui_reduced" else None
        probe = None
        stop_reason = None
        try:
            if control:
                # Both A/B orders must start with the same real OS setting.
                # Missing control clipboard support remains deliberately untested.
                control.prepare()
            print("Running", name, "with", " ".join(command), flush=True)
            probe = subprocess.Popen(command)
            try:
                if probe.wait(timeout=540):
                    failed.append(name)
                try:
                    outcome = json.loads((args.output / name / "outcome.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    outcome = {}
                if (outcome.get("cleanup_status") not in ("clean", "not_needed")
                        or outcome.get("cleanup_survivors") or outcome.get("process_access_denied_pids")
                        or outcome.get("desktop_integration", {}).get("cleanup", {}).get("status") == "failed"):
                    if name not in failed:
                        failed.append(name)
                    stop_reason = "Process/desktop cleanup failed, unknown or missing; later candidates refused"
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
                if name not in failed:
                    failed.append(name)
                (args.output / name).mkdir(exist_ok=True)
                stop_reason = "Probe exceeded 540s watchdog; subsequent candidates refused to avoid contamination"
                write_json(args.output / name / "watchdog.json", dict(
                    name=name, status="failed", cleanup_status="unknown", reason=stop_reason))
        except Exception as error:
            if name not in failed:
                failed.append(name)
            stop_reason = f"Runner prerequisite/launch/cleanup error: {type(error).__name__}: {error}"
            (args.output / name).mkdir(exist_ok=True)
            write_json(args.output / name / "runner-error.json", dict(name=name, status="failed", reason=stop_reason))
        finally:
            if control:
                control_ok = control.close()
                outcome_path = args.output / name / "outcome.json"
                try:
                    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    outcome = dict(name=name, status="not_run" if probe is None else "failed",
                                   measurement_profile="diagnostic-reduced", phases={},
                                   cleanup_status="not_needed" if probe is None else "unknown",
                                   reason=stop_reason or "Reduced control produced no native outcome")
                outcome["control_system_theme"] = control.result
                if not control_ok:
                    if name not in failed:
                        failed.append(name)
                    stop_reason = "Reduced control OS preference or restoration unverified; later candidates refused"
                    outcome.update(status="failed", reason=stop_reason)
                elif stop_reason:
                    # A watchdog or runner failure cannot leave a stale passing result.
                    outcome.update(status="failed", reason=stop_reason)
                write_json(outcome_path, outcome)
        if stop_reason:
            write_json(args.output / "stopped-after.json", dict(name=name, reason=stop_reason))
            break
    write_json(args.output / "failed-candidates.json", failed)
    # The workflow uploads all evidence before running the strict verification gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
