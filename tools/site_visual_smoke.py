#!/usr/bin/env python3
"""Capture the real site with the CI runner's existing, sandboxed Google Chrome.

No browser download, fabricated dataset, public server or sandbox-disabling flags.
This is a browser/DOM smoke check; a reviewer must inspect the saved screenshots.
"""
from __future__ import annotations

import argparse
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
CHROME_FLAGS = ("--headless", "--no-first-run", "--no-default-browser-check",
                "--disable-background-networking", "--force-device-scale-factor=1",
                "--virtual-time-budget=5000")
CHROME_TIMEOUT_SECONDS = 45


def capture_fragment(dataset_present):
    """Keep the actual result tables in view instead of the explanatory preamble."""
    return "#desktop-results" if dataset_present else "#desktop"


def inspect_dom(html, dataset_present, expected_cards=5):
    class Counts(HTMLParser):
        cards = tables = errors = 0

        def handle_starttag(self, tag, attrs):
            classes = set(dict(attrs).get("class", "").split())
            self.cards += tag == "article" and "fw" in classes
            self.tables += tag == "table" and "desktop-table" in classes
            self.errors += "error" in classes

    counts = Counts()
    counts.feed(html)
    checks = dict(historical_cards=counts.cards, desktop_tables=counts.tables,
                  rendered_error_elements=counts.errors,
                  desktop_table_assertion="required" if dataset_present else "skipped: desktop-results.json is absent")
    checks["status"] = "passed" if counts.cards == expected_cards and not counts.errors \
        and (not dataset_present or counts.tables == 3) else "failed"
    return checks


def run_chrome(binary, profile, arguments, output, name, *, dbus_session, invocations):
    """Bound each invocation and clean only the process group we created."""
    evidence = dict(name=name, status="failed", timeout_seconds=CHROME_TIMEOUT_SECONDS,
                    session="isolated D-Bus session; Chrome sandbox enabled")
    invocations.append(evidence)
    started = time.monotonic()
    try:
        with (output / f"{name}.html").open("wb") as stdout, (output / f"{name}.log").open("wb") as stderr:
            # Hosted runners need not have a usable desktop session bus. Starting
            # one for this invocation avoids Chromium waiting on a malformed or
            # unavailable inherited address; no browser sandbox is disabled.
            process = subprocess.Popen([dbus_session, "--", binary, *CHROME_FLAGS,
                                        f"--user-data-dir={profile}", *arguments],
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                code = process.wait(timeout=CHROME_TIMEOUT_SECONDS)
                evidence["returncode"] = code
                if code:
                    raise RuntimeError(f"Chrome {name} exited with status {code}; see {name}.log")
            finally:
                # An isolated group contains this launch and its session bus,
                # never another job's browser or the runner's desktop services.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
        evidence["status"] = "passed"
    except subprocess.TimeoutExpired as error:
        evidence["timed_out"] = True
        evidence["reason"] = str(error)
        raise
    except Exception as error:
        evidence["reason"] = str(error)
        raise
    finally:
        evidence["elapsed_seconds"] = round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/site-visual")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    dataset_present = (ROOT / "data/desktop-results.json").is_file()
    report = dict(schema_version=1, status="failed", dataset_present=dataset_present,
                  target_fragment=capture_fragment(dataset_present),
                  scope="actual imported desktop evidence" if dataset_present else "baseline only; current-results table assertion skipped",
                  limitations=["Screenshots require human visual inspection; DOM readiness is not visual approval.",
                               "This checks the comparison website, not native application acceptance or memory."])
    try:
        binary = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
        if not binary:
            raise RuntimeError("The runner's Google Chrome is missing; no browser will be installed")
        dbus_session = shutil.which("dbus-run-session")
        if not dbus_session:
            raise RuntimeError("The runner's dbus-run-session is missing; cannot create an isolated browser session")
        report["chrome_binary"] = str(Path(binary).resolve())
        report["dbus_session_binary"] = str(Path(dbus_session).resolve())
        report["browser_invocations"] = []
        report["chrome_version"] = subprocess.check_output([binary, "--version"], text=True, timeout=10).strip()
        report["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10).strip()
        report["runner_image"] = os.environ.get("ImageVersion", "")
        expected_cards = len(json.loads((ROOT / "data/features.json").read_text(encoding="utf-8"))["frameworks"])
        with (output / "server.log").open("w", encoding="utf-8") as server_log:
            class Handler(SimpleHTTPRequestHandler):
                def log_message(self, format, *values):
                    server_log.write(f"{self.address_string()} {format % values}\n")
                    server_log.flush()

            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(ROOT)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/{report['target_fragment']}"
                with tempfile.TemporaryDirectory(prefix="site-chrome-") as profile:
                    run_chrome(binary, profile, ["--dump-dom", url], output, "rendered-dom",
                               dbus_session=dbus_session, invocations=report["browser_invocations"])
                    report["dom"] = inspect_dom((output / "rendered-dom.html").read_text(encoding="utf-8"), dataset_present, expected_cards)
                    report["screenshots"] = []
                    for name, width, height in (("desktop", 1440, 2400), ("narrow", 560, 2400)):
                        capture = output / f"{name}.png"
                        run_chrome(binary, profile, [f"--window-size={width},{height}", f"--screenshot={capture}", url], output, name,
                                   dbus_session=dbus_session, invocations=report["browser_invocations"])
                        header = capture.read_bytes()[:24]
                        if not header.startswith(b"\x89PNG\r\n\x1a\n") or len(header) < 24:
                            raise RuntimeError(f"Chrome did not produce a PNG: {capture.name}")
                        report["screenshots"].append(dict(file=capture.name, requested_width=width, requested_height=height,
                                                          width=int.from_bytes(header[16:20], "big"), height=int.from_bytes(header[20:24], "big")))
                if report["dom"]["status"] != "passed":
                    raise RuntimeError("Rendered DOM is incomplete; inspect readiness.json and screenshots")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
        report["status"] = "passed"
    except Exception as error:
        report["reason"] = str(error)
    (output / "readiness.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
