"""Focused contracts for paired native-backend proof and memory accounting."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from linux_display_probe import display_environment, read_diagnostic, summary, run_matrix


class DisplayProbeTests(unittest.TestCase):
    def exercise_preflight_failure(self, cleanup):
        with tempfile.TemporaryDirectory(dir='/tmp') as directory:
            output = Path(directory)
            args = SimpleNamespace(output=output, target=output, user='fixture',
                                   framework='egui', backend='both', settle=2, intervals=1, keep_going=True)
            def launch(command, **kwargs):
                case = command[command.index('--case') + 1]
                folder = output/case
                folder.mkdir()
                failed = case.endswith('x11')
                outcome = dict(status='failed' if failed else 'passed', cleanup_status=cleanup if failed else 'clean',
                               cleanup_survivors=[], binary_sha256='same-binary')
                (folder/'outcome.json').write_text(json.dumps(outcome))
                return SimpleNamespace(returncode=1 if failed else 0)
            with patch('linux_display_probe.subprocess.run', side_effect=launch) as run:
                self.assertEqual(run_matrix(args), 1)
            return run.call_count, json.loads((output/'matrix-outcome.json').read_text())

    def test_preflight_collects_independent_failure_after_clean_cleanup(self):
        calls, outcome = self.exercise_preflight_failure('clean')
        self.assertEqual(calls, 2)
        self.assertEqual(outcome['failed_cases'], ['egui-x11'])
        self.assertEqual(outcome['completed_cases'], ['egui-x11', 'egui-wayland'])
        self.assertEqual(outcome['status'], 'failed')

    def test_preflight_refuses_next_case_when_cleanup_unknown(self):
        calls, outcome = self.exercise_preflight_failure('unknown')
        self.assertEqual(calls, 1)
        self.assertIn('cleanup failed or unknown', outcome['stopped_reason'])

    def test_other_display_and_renderer_override_are_removed(self):
        env = display_environment(dict(DISPLAY=':7', WAYLAND_DISPLAY='wayland-7', WAYLAND_SOCKET='8',
                                      GSK_RENDERER='cairo', WLR_XWAYLAND='0'), 'wayland')
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'WAYLAND_SOCKET', 'GSK_RENDERER', 'WLR_XWAYLAND'):
            self.assertNotIn(key, env)
        self.assertEqual(env['GDK_BACKEND'], 'wayland')
        self.assertEqual(env['QT_QPA_PLATFORM'], 'wayland')
        self.assertEqual(env['LIBGL_ALWAYS_SOFTWARE'], '1')

    def test_actual_backend_and_content_size_are_required(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as directory:
            path = Path(directory)/'app.log'
            data = dict(name='egui', backend='x11', ready=True, content_width=960, content_height=640)
            path.write_text('DISPLAY_DIAGNOSTIC '+json.dumps(data))
            with self.assertRaisesRegex(RuntimeError, 'backend/name mismatch'):
                read_diagnostic(path,'egui','wayland')
            data.update(backend='wayland', content_height=612)
            path.write_text('DISPLAY_DIAGNOSTIC '+json.dumps(data))
            with self.assertRaisesRegex(RuntimeError, 'content is not ready'):
                read_diagnostic(path,'egui','wayland')
            data['content_height'] = 640
            path.write_text('DISPLAY_DIAGNOSTIC '+json.dumps(data))
            self.assertEqual(read_diagnostic(path,'egui','wayland'),data)

    def test_family_pss_and_cpu_include_new_helper_after_baseline(self):
        def process(pid, created, cpu, rss, pss):
            return dict(pid=pid,created=created,cpu_seconds=cpu,threads=1,
                        rollup_kib=dict(Rss=rss,Pss=pss),stat_rss_bytes=rss*1024)
        rows=[dict(monotonic=1,wall_time=100,processes=[process(1,90,10,1024,512)],family_rss_bytes=2**20),
              dict(monotonic=3,wall_time=102,processes=[process(1,90,10.1,1024,512),process(2,101,.2,1024,256)],family_rss_bytes=2**21)]
        result=summary(rows)
        self.assertEqual(result['family_pss_mib']['median'],.75)
        self.assertEqual(result['family_rss_mib']['median'],2)
        self.assertEqual(result['max_processes'],2)
        self.assertAlmostEqual(result['observed_cpu_percent_one_core'],15)
        rows[-1]['processes'][-1]['created']=99
        with self.assertRaisesRegex(RuntimeError,'Late helper discovery'):
            summary(rows)


if __name__ == '__main__':
    unittest.main()
