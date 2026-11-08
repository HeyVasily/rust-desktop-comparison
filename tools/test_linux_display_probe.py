"""Focused contracts for paired native-backend proof and memory accounting."""
import json
from pathlib import Path
import tempfile
import unittest

from linux_display_probe import display_environment, read_diagnostic, summary


class DisplayProbeTests(unittest.TestCase):
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
