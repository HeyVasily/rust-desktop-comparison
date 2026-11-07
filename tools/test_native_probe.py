"""Host-free regressions for native footprint accounting and blank-client refusal."""
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

import native_probe as probe


class NativeProbeTests(unittest.TestCase):
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
