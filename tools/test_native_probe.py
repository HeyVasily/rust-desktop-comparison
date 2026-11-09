"""Host-free regressions for native footprint accounting and blank-client refusal."""
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

import native_probe as probe


class NativeProbeTests(unittest.TestCase):
    def test_reduced_control_uses_same_foreground_driver_without_desktop_acceptance(self):
        evidence = dict(status="passed", requested_pid=42, observed_pid="42")
        driver = Mock(focus=Mock(return_value=evidence), last_focus=evidence)
        result = dict(measurement_profile="diagnostic-reduced")
        window = dict(pid=42, id=123)
        with patch("desktop_probe.DesktopInput", return_value=driver):
            probe.activate_reduced_control(window, result)
        driver.focus.assert_called_once_with(window)
        self.assertEqual(result["startup_focus"], evidence)
        self.assertNotIn("desktop_integration", result)

    def test_reduced_control_foreground_failure_is_preserved_and_propagates(self):
        from desktop_probe import DesktopEnvironmentError
        evidence = dict(status="environment_error", observed_pid="7")
        driver = Mock(focus=Mock(side_effect=DesktopEnvironmentError("wrong foreground")), last_focus=evidence)
        result = {}
        with patch("desktop_probe.DesktopInput", return_value=driver):
            with self.assertRaisesRegex(DesktopEnvironmentError, "wrong foreground"):
                probe.activate_reduced_control(dict(pid=42, id=123), result)
        self.assertEqual(result["startup_focus"], evidence)

    def test_linux_window_discovery_uses_explicit_case_display_for_every_command(self):
        case_env = dict(DISPLAY=':91')
        def output(command, **kwargs):
            self.assertIs(kwargs.get('env'), case_env)
            if command[0] == 'xwininfo':
                return 'Map State: IsViewable'
            if command[1] == 'getwindowname':
                return 'Example'
            return 'X=160\nY=40\nWIDTH=960\nHEIGHT=640\n'
        with patch.object(probe.sys, 'platform', 'linux'), \
                patch.dict(os.environ, DISPLAY=':wrong'), \
                patch.object(probe.subprocess, 'run', return_value=Mock(stdout='123')) as search, \
                patch.object(probe.subprocess, 'check_output', side_effect=output) as inspect:
            window = probe.find_window({321}, 'Example', env=case_env)
        self.assertIs(search.call_args.kwargs['env'], case_env)
        self.assertEqual(inspect.call_count, 3)
        self.assertEqual(window['rectangle'], [160, 40, 1120, 680])

    def test_verified_other_owner_is_excluded_from_global_webkit_audit(self):
        family = Mock()
        family.root.pid = 10
        family.observed = {}
        report = dict(complete=True, unrelated_helpers=[dict(pid=20, created=2.0, responsible_pid=7)])
        family.external_scope.report.return_value = report
        helpers = {'20:2.0': dict(pid=20, create_time=2.0, name='WebKit')}
        with patch.object(probe, 'web_helpers', return_value=helpers):
            unassigned, snapshot = probe.scope_snapshot(family, {})
        self.assertEqual(unassigned, {})
        self.assertEqual(snapshot, report)

    def test_unrelated_pid_reuse_does_not_hide_unattributed_helper(self):
        family = Mock()
        family.root.pid = 10
        family.observed = {}
        family.external_scope.report.return_value = dict(
            complete=True, unrelated_helpers=[dict(pid=20, created=1.0, responsible_pid=7)])
        helpers = {'20:2.0': dict(pid=20, create_time=2.0, name='WebKit')}
        with patch.object(probe, 'web_helpers', return_value=helpers):
            unassigned, _ = probe.scope_snapshot(family, {})
        self.assertEqual(unassigned, helpers)

    def test_windows_csd_surface_is_not_accepted_as_requested_client(self):
        family = Mock()
        family.refresh.return_value = []
        window = dict(id=1, rectangle=[8, 8, 996, 677])
        with patch.object(probe, 'find_window', return_value=window):
            with self.assertRaisesRegex(RuntimeError, 'Client size'):
                probe.phase(family, 'GTK', Path('/unused'), 'diagnostic', 0, 1,
                            client_size=[960, 640])

    def test_geometry_change_during_sampling_is_refused(self):
        family = Mock()
        family.refresh.return_value = []
        family.sample.side_effect = [
            dict(monotonic=1, processes=[], family_rss_bytes=1),
            dict(monotonic=2, processes=[], family_rss_bytes=1),
        ]
        windows = [dict(id=1, rectangle=[16, 39, 976, 679]),
                   dict(id=1, rectangle=[16, 39, 976, 678])]
        with tempfile.TemporaryDirectory(dir='/tmp' if os.name != 'nt' else None) as directory:
            with patch.object(probe, 'find_window', side_effect=windows), \
                    patch.object(probe, 'capture', return_value={}), \
                    patch.object(probe.time, 'sleep'):
                with self.assertRaisesRegex(RuntimeError, 'geometry changed'):
                    probe.phase(family, 'app', Path(directory), 'comparison', 0, 1,
                                client_size=[960, 640])

    def test_cpu_counters_are_qualified_by_creation_time(self):
        def process(pid, created, cpu):
            return dict(pid=pid, created=created, cpu_seconds=cpu)
        rows = [
            dict(monotonic=1, processes=[process(10, 1, 9)], family_rss_bytes=1),
            dict(monotonic=2, processes=[process(10, 1, 9.1), process(11, 2, .2)], family_rss_bytes=2**20),
            dict(monotonic=3, processes=[process(10, 3, .3)], family_rss_bytes=3*2**20),
        ]
        summary = probe.summarize(rows)
        self.assertAlmostEqual(summary['observed_cpu_percent_one_core'], 30)
        self.assertEqual(summary['family_rss_mib']['median'], 2)
        self.assertEqual(summary['family_rss_mib']['p95'], 3)

    def test_primary_memory_is_summarized_beside_rss(self):
        rows = [dict(monotonic=t, processes=[], family_rss_bytes=8 * 2**20,
                     family_primary_bytes=t * 2**20) for t in (1, 2, 3, 4)]
        summary = probe.summarize(rows)
        self.assertEqual(summary['family_rss_mib']['median'], 8)
        self.assertEqual(summary['family_primary_mib']['median'], 3)
        self.assertEqual(summary['family_primary_mib']['observed_maximum'], 4)

    def test_primary_metric_is_named_per_platform(self):
        for platform, name in (('linux', 'Linux PSS'), ('darwin', 'macOS physical footprint'),
                               ('win32', 'Windows private working set')):
            with patch.object(probe.sys, 'platform', platform):
                self.assertEqual(probe.primary_metric_name(), name)

    def test_late_discovery_does_not_charge_pre_phase_cpu(self):
        rows = [dict(monotonic=1, wall_time=100, processes=[], family_rss_bytes=1),
                dict(monotonic=2, wall_time=101, family_rss_bytes=1,
                     processes=[dict(pid=10, created=90, cpu_seconds=200)]),
                dict(monotonic=3, wall_time=102, family_rss_bytes=1,
                     processes=[dict(pid=10, created=90, cpu_seconds=200.2)])]
        summary = probe.summarize(rows)
        self.assertAlmostEqual(summary['observed_cpu_percent_one_core'], 10)
        self.assertEqual(summary['late_discovered_preexisting_processes'], ['10:90'])

    def test_titlebar_does_not_validate_blank_client(self):
        with tempfile.TemporaryDirectory(dir='/tmp' if os.name != 'nt' else None) as directory:
            path = Path(directory) / 'capture.png'
            image = Image.new('RGB', (960, 668), 'black')
            ImageDraw.Draw(image).rectangle((0, 0, 959, 28), fill='white')
            def capture(*args, **kwargs):
                image.save(path)
            with patch.object(probe.sys, 'platform', 'linux'), patch.object(probe.subprocess, 'run', side_effect=capture):
                with self.assertRaisesRegex(RuntimeError, 'near-uniform'):
                    probe.capture_once(dict(id=1), path)

    def test_rendered_client_is_accepted(self):
        with tempfile.TemporaryDirectory(dir='/tmp' if os.name != 'nt' else None) as directory:
            path = Path(directory) / 'capture.png'
            image = Image.new('RGB', (960, 640), 'white')
            ImageDraw.Draw(image).rectangle((40, 80, 200, 600), fill='gray')
            def capture(*args, **kwargs):
                image.save(path)
            with patch.object(probe.sys, 'platform', 'linux'), patch.object(probe.subprocess, 'run', side_effect=capture):
                self.assertEqual(probe.capture_once(dict(id=1), path)['width'], 960)


if __name__ == '__main__':
    unittest.main()
