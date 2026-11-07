"""Attribute WKWebView XPC services with macOS process responsibility metadata.

Private interfaces are checked at runtime and failures prevent a complete scope.
Coalition IDs are audit evidence only: a shell and its children can share a
resource coalition, so coalition equality is not sufficient ownership evidence.

ABI sources:
https://chromium.googlesource.com/chromium/src/+/refs/tags/134.0.6998.28/base/process/process_info_mac.mm
https://chromium.googlesource.com/chromium/src/+/refs/tags/100.0.4896.200/base/process/launch_mac.cc
https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/proc_info_private.h
https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/mach/coalition.h
"""

import ctypes
import errno
import os
from pathlib import Path
import subprocess
import sys

import psutil


_LAUNCHER = r"""
#include <dlfcn.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern char **environ;

int main(int argc, char **argv) {
    if (argc < 2) return 64;
    int (*disclaim)(posix_spawnattr_t, int) =
        dlsym(RTLD_DEFAULT, "responsibility_spawnattrs_setdisclaim");
    if (!disclaim) {
        fputs("macOS responsibility spawn API unavailable\n", stderr);
        return 69;
    }
    posix_spawnattr_t attributes;
    int error = posix_spawnattr_init(&attributes);
    if (error) {
        fprintf(stderr, "posix_spawnattr_init: %s\n", strerror(error));
        return 71;
    }
    error = posix_spawnattr_setflags(&attributes, POSIX_SPAWN_SETEXEC);
    if (!error) error = disclaim(&attributes, 1);
    pid_t pid = 0;
    if (!error) error = posix_spawn(&pid, argv[1], NULL, &attributes, argv + 1, environ);
    posix_spawnattr_destroy(&attributes);
    fprintf(stderr, "macOS responsibility launch: %s\n", strerror(error));
    return 71;
}
"""


def launch_command(executable, output_dir):
    """Build an exec-in-place launcher before starting the measured process.

    Popen's PID remains the application's PID. Disclaiming responsibility is a
    request, not proof: MacOSProcessScope independently verifies the result.
    """
    if sys.platform != "darwin":
        raise RuntimeError("macOS responsibility launcher requires Darwin")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = output / "responsibility-launcher.c"
    binary = output / "responsibility-launcher"
    source.write_text(_LAUNCHER, encoding="utf-8")
    compiled = subprocess.run(
        ["/usr/bin/cc", "-O2", "-Wall", "-Wextra", str(source), "-o", str(binary)],
        capture_output=True, text=True, timeout=60)
    (output / "responsibility-launcher-build.log").write_text(
        compiled.stdout + compiled.stderr, encoding="utf-8")
    if compiled.returncode:
        raise RuntimeError("macOS responsibility launcher compilation failed; inspect build log")
    return [str(binary), str(Path(executable).resolve())]


class _CoalitionInfo(ctypes.Structure):
    _fields_ = [("ids", ctypes.c_uint64 * 2), ("reserved", ctypes.c_uint64 * 3)]


class MacOSMetadata:
    def __init__(self):
        if sys.platform != "darwin":
            raise RuntimeError("macOS process metadata requires Darwin")
        self.system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        try:
            self._responsible = self.system.responsibility_get_pid_responsible_for_pid
        except AttributeError as error:
            raise RuntimeError("macOS process responsibility API unavailable") from error
        self._responsible.argtypes = [ctypes.c_int]
        self._responsible.restype = ctypes.c_int
        self.proc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        self.proc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                          ctypes.c_void_p, ctypes.c_int]
        self.proc.proc_pidinfo.restype = ctypes.c_int

    def responsible(self, pid):
        ctypes.set_errno(0)
        responsible = self._responsible(pid)
        if responsible <= 0:
            code = ctypes.get_errno() or errno.EIO
            raise OSError(code, f"responsibility lookup failed for PID {pid}")
        return responsible

    def coalitions(self, pid):
        info = _CoalitionInfo()
        ctypes.set_errno(0)
        count = self.proc.proc_pidinfo(pid, 20, 0, ctypes.byref(info), ctypes.sizeof(info))
        if count != ctypes.sizeof(info):
            code = ctypes.get_errno() or errno.EIO
            raise OSError(code, f"coalition lookup returned {count} bytes for PID {pid}")
        return {"resource": info.ids[0], "jetsam": info.ids[1]}


def _identity(process):
    return f"{process.pid}:{process.create_time()}"


class MacOSProcessScope:
    """Discover WebKit services whose responsible PID is the live application.

    The caller combines these with ordinary ancestry, retains process objects,
    and performs its normal CPU/RSS reads and cleanup. Sampling cannot capture
    processes that start and exit between polls. No shared system daemon costs
    are allocated. Injected metadata/iterator support host-free attribution tests.
    """

    def __init__(self, root, metadata=None, process_iter=None):
        self.root = root
        self.root_identity = _identity(root)
        self.metadata = metadata if metadata is not None else MacOSMetadata()
        self.process_iter = process_iter if process_iter is not None else psutil.process_iter
        self.root_evidence = {"pid": root.pid, "created": root.create_time()}
        self.root_self_responsible = False
        self.attributed = {}
        self.unrelated = {}
        self.errors = set()
        self.coalition_errors = set()

    def _coalitions(self, pid):
        try:
            return self.metadata.coalitions(pid)
        except OSError as error:
            self.coalition_errors.add(str(error))
            return None

    def refresh(self):
        if not self.root.is_running() or _identity(self.root) != self.root_identity:
            self.errors.add("Application identity disappeared during scope discovery")
            self.root_self_responsible = False
            return []
        try:
            responsible = self.metadata.responsible(self.root.pid)
        except OSError as error:
            self.errors.add(str(error))
            self.root_self_responsible = False
            return []
        self.root_self_responsible = responsible == self.root.pid
        self.root_evidence.update(responsible_pid=responsible,
                                  coalitions=self._coalitions(self.root.pid))
        if not self.root_self_responsible:
            # Popen can return before the launcher executes the app. A later
            # refresh may establish self-responsibility; do not latch this race.
            return []
        own = []
        for process in self.process_iter(["pid", "name"]):
            name = process.info.get("name") or ""
            if "webkit" not in name.lower():
                continue
            try:
                identity = _identity(process)
                responsible = self.metadata.responsible(process.pid)
                record = {"pid": process.pid, "name": name,
                          "created": process.create_time(), "responsible_pid": responsible,
                          "coalitions": self._coalitions(process.pid)}
                # PID reuse or exit during metadata lookup cannot grant ownership.
                if not process.is_running() or _identity(process) != identity:
                    continue
                if responsible == self.root.pid:
                    record["attribution"] = "responsible_pid_equals_live_application_pid"
                    self.attributed[identity] = record
                    self.unrelated.pop(identity, None)
                    own.append(process)
                else:
                    self.unrelated[identity] = record
                    if identity in self.attributed:
                        self.errors.add(f"Attributed helper changed responsibility: {identity}")
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            except psutil.AccessDenied:
                self.errors.add(f"Denied access to WebKit helper PID {process.pid}")
            except OSError as error:
                # A process disappearing between enumeration and native metadata
                # retrieval is an ordinary race; all other errors are material.
                if error.errno != errno.ESRCH:
                    self.errors.add(str(error))
        return own

    def report(self, require_webcontent=True):
        webcontent = any("webcontent" in row["name"].lower()
                         for row in self.attributed.values())
        errors = set(self.errors)
        if not self.root_self_responsible:
            errors.add("Application is not verified as its own responsible process")
        if require_webcontent and not webcontent:
            errors.add("No application-owned WebKit WebContent process was observed")
        return {"complete": not errors,
                "method": "Ancestry plus macOS responsibility PID; coalitions recorded as evidence only",
                "root_self_responsible": self.root_self_responsible,
                "root": dict(self.root_evidence),
                "attributed_helpers": list(self.attributed.values()),
                "unrelated_helpers": list(self.unrelated.values()),
                "errors": sorted(errors),
                "coalition_metadata_errors": sorted(self.coalition_errors),
                "limitations": [
                    "Private macOS responsibility API; validated on each measured run",
                    "WebKit services are discovered by process name and attributed by responsible PID",
                    "Polling can miss short-lived services; shared system daemons are excluded",
                    "Summed per-process RSS can double-count shared pages"]}
