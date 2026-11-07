"""Host-free ownership checks; native macOS APIs still require runner validation."""

import errno
import unittest

import psutil

from macos_process_scope import MacOSProcessScope


class Process:
    def __init__(self, pid, name="application", created=1):
        self.pid = pid
        self.created = created
        self.alive = True
        self.state = psutil.STATUS_RUNNING
        self.info = {"pid": pid, "name": name}
        self.identity_error = None

    def create_time(self):
        if self.identity_error:
            raise self.identity_error
        return self.created

    def is_running(self):
        return self.alive

    def status(self):
        return self.state


class Metadata:
    def __init__(self, owners):
        self.owners = owners
        self.on_query = {}
        self.coalition_error = None

    def responsible(self, pid):
        if pid in self.on_query:
            self.on_query[pid]()
        result = self.owners[pid]
        if isinstance(result, Exception):
            raise result
        return result

    def coalitions(self, pid):
        if self.coalition_error:
            raise self.coalition_error
        # Deliberately shared by the application and unrelated helpers.
        return {"resource": 123, "jetsam": 456}


class MacOSProcessScopeTests(unittest.TestCase):
    def setUp(self):
        self.root = Process(10)
        self.webcontent = Process(20, "com.apple.WebKit.WebContent")
        self.unrelated = Process(30, "com.apple.WebKit.GPU")
        self.metadata = Metadata({10: 10, 20: 10, 30: 999})
        self.processes = [self.webcontent, self.unrelated]
        self.scope = MacOSProcessScope(
            self.root, self.metadata, lambda attributes: self.processes)

    def test_exact_responsible_pid_admits_helper(self):
        self.assertEqual(self.scope.refresh(), [self.webcontent])
        report = self.scope.report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["attributed_helpers"][0]["pid"], 20)
        self.assertEqual(report["attributed_helpers"][0]["responsible_pid"], 10)
        self.assertEqual(report["unrelated_helpers"][0]["pid"], 30)

    def test_shared_coalition_does_not_establish_ownership(self):
        self.metadata.owners[20] = 999
        self.assertEqual(self.scope.refresh(), [])
        report = self.scope.report()
        self.assertFalse(report["complete"])
        self.assertEqual(report["attributed_helpers"], [])
        self.assertEqual(len(report["unrelated_helpers"]), 2)
        for helper in report["unrelated_helpers"]:
            self.assertEqual(helper["coalitions"], report["root"]["coalitions"])

    def test_inherited_responsibility_refuses_scope(self):
        self.metadata.owners.update({10: 999, 20: 999})
        self.assertEqual(self.scope.refresh(), [])
        report = self.scope.report(require_webcontent=False)
        self.assertFalse(report["complete"])
        self.assertFalse(report["root_self_responsible"])
        self.assertEqual(report["attributed_helpers"], [])

    def test_preexec_transition_does_not_latch_failure(self):
        self.metadata.owners[10] = 999
        self.assertEqual(self.scope.refresh(), [])
        self.assertFalse(self.scope.report()["complete"])
        self.metadata.owners[10] = 10
        self.assertEqual(self.scope.refresh(), [self.webcontent])
        self.assertTrue(self.scope.report()["complete"])

    def test_native_metadata_denial_refuses_scope(self):
        self.metadata.owners[20] = OSError(errno.EACCES, "metadata access denied")
        self.assertEqual(self.scope.refresh(), [])
        report = self.scope.report(require_webcontent=False)
        self.assertFalse(report["complete"])
        self.assertTrue(any("metadata access denied" in error for error in report["errors"]))

    def test_psutil_denial_refuses_scope(self):
        self.webcontent.identity_error = psutil.AccessDenied(self.webcontent.pid)
        self.assertEqual(self.scope.refresh(), [])
        report = self.scope.report(require_webcontent=False)
        self.assertFalse(report["complete"])
        self.assertIn("Denied access to WebKit helper PID 20", report["errors"])

    def test_root_metadata_failure_refuses_scope(self):
        self.metadata.owners[10] = OSError(errno.EIO, "root metadata failed")
        self.assertEqual(self.scope.refresh(), [])
        self.assertFalse(self.scope.report(require_webcontent=False)["complete"])

    def test_exiting_helper_does_not_create_false_access_failure(self):
        self.metadata.owners[30] = OSError(errno.ESRCH, "process exited")
        self.metadata.on_query[30] = lambda: setattr(self.unrelated, "alive", False)
        self.assertEqual(self.scope.refresh(), [self.webcontent])
        self.assertTrue(self.scope.report()["complete"])

    def test_unknown_helper_permission_failure_then_exit_is_audited(self):
        self.metadata.owners[30] = OSError(errno.EPERM, "helper lookup denied")
        self.scope.refresh()
        self.assertFalse(self.scope.report()["complete"])
        self.unrelated.alive = False
        report = self.scope.report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["pending_unattributed_helpers"], [])
        vanished = report["vanished_unattributed_helpers"]
        self.assertEqual(len(vanished), 1)
        self.assertEqual(vanished[0]["identity"], "30:1")
        self.assertEqual(vanished[0]["pid"], 30)
        self.assertIn("helper lookup denied", vanished[0]["lookup_errors"][0])

    def test_unknown_live_helper_permission_failure_still_refuses(self):
        self.metadata.owners[30] = OSError(errno.EPERM, "helper lookup denied")
        self.scope.refresh()
        self.scope.refresh()
        report = self.scope.report()
        self.assertFalse(report["complete"])
        self.assertEqual(report["pending_unattributed_helpers"][0]["lookup_attempts"], 2)
        self.assertEqual(report["vanished_unattributed_helpers"], [])

    def test_unknown_helper_permission_failure_then_zombie_is_audited(self):
        self.metadata.owners[30] = OSError(errno.EPERM, "helper lookup denied")
        self.scope.refresh()
        self.assertFalse(self.scope.report()["complete"])
        self.unrelated.state = psutil.STATUS_ZOMBIE
        report = self.scope.report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["pending_unattributed_helpers"], [])
        self.assertEqual(report["vanished_unattributed_helpers"][0]["identity"], "30:1")

    def test_unknown_permission_failure_then_verified_unrelated_clears_pending(self):
        self.metadata.owners[30] = OSError(errno.EPERM, "helper lookup denied")
        self.scope.refresh()
        self.metadata.owners[30] = 999
        self.assertEqual(self.scope.refresh(), [self.webcontent])
        report = self.scope.report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["pending_unattributed_helpers"], [])
        self.assertEqual(report["unrelated_helpers"][0]["identity"], "30:1")
        self.assertEqual(report["unrelated_helpers"][0]["responsible_pid"], 999)

    def test_attributed_helper_permission_failure_remains_fatal_after_exit(self):
        self.scope.refresh()
        self.metadata.owners[20] = OSError(errno.EPERM, "owned helper lookup denied")
        self.scope.refresh()
        self.webcontent.alive = False
        self.assertFalse(self.scope.report()["complete"])
        self.assertEqual(self.scope.report()["pending_unattributed_helpers"], [])

    def test_attributed_helper_exit_does_not_become_access_denial(self):
        self.scope.refresh()
        self.metadata.owners[20] = OSError(errno.ESRCH, "owned helper exited")
        self.metadata.on_query[20] = lambda: setattr(self.webcontent, "alive", False)
        self.scope.refresh()
        self.assertTrue(self.scope.report()["complete"])

    def test_pending_pid_reuse_does_not_transfer_ownership(self):
        self.metadata.owners[30] = OSError(errno.EPERM, "helper lookup denied")
        self.scope.refresh()
        self.unrelated.created = 2
        self.metadata.owners[30] = 999
        self.scope.refresh()
        report = self.scope.report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["vanished_unattributed_helpers"][0]["identity"], "30:1")
        self.assertEqual(report["unrelated_helpers"][0]["identity"], "30:2")
        self.assertEqual([p["pid"] for p in report["attributed_helpers"]], [20])

    def test_root_pid_reuse_refuses_scope(self):
        self.scope.refresh()
        self.root.created = 2
        self.assertEqual(self.scope.refresh(), [])
        report = self.scope.report()
        self.assertFalse(report["complete"])
        self.assertIn("Application identity disappeared during scope discovery", report["errors"])

    def test_helper_pid_reuse_during_lookup_does_not_grant_ownership(self):
        self.metadata.on_query[20] = lambda: setattr(self.webcontent, "created", 2)
        self.assertEqual(self.scope.refresh(), [])
        report = self.scope.report()
        self.assertEqual(report["attributed_helpers"], [])
        self.assertFalse(report["complete"])

    def test_responsibility_change_latches_refusal(self):
        self.scope.refresh()
        self.metadata.owners[20] = 999
        self.assertEqual(self.scope.refresh(), [])
        self.assertFalse(self.scope.report()["complete"])
        self.metadata.owners[20] = 10
        self.scope.refresh()
        self.assertFalse(self.scope.report()["complete"])

    def test_missing_webcontent_refuses_webview_scope(self):
        self.processes.clear()
        self.scope.refresh()
        self.assertFalse(self.scope.report()["complete"])
        self.assertTrue(self.scope.report(require_webcontent=False)["complete"])

    def test_optional_coalition_error_is_reported_without_losing_pid_evidence(self):
        self.metadata.coalition_error = OSError(errno.ENOTSUP, "coalition unavailable")
        self.assertEqual(self.scope.refresh(), [self.webcontent])
        report = self.scope.report()
        self.assertTrue(report["complete"])
        self.assertIsNone(report["attributed_helpers"][0]["coalitions"])
        self.assertTrue(report["coalition_metadata_errors"])


if __name__ == "__main__":
    unittest.main()
