"""Small accounting regressions for the controlled Linux memory diagnostic."""
import unittest
from gtk_memory_probe import parse_smaps, summarize


class MemoryAccountingTests(unittest.TestCase):
    def test_mapping_groups_sum_repeated_files_and_keep_anonymous(self):
        text = '''1000-2000 r--p 00000000 08:01 1 /lib/a.so
Rss: 10 kB
Pss: 5 kB
Private_Clean: 2 kB
2000-3000 r-xp 00001000 08:01 1 /lib/a.so
Rss: 20 kB
Pss: 12 kB
3000-4000 rw-p 00000000 00:00 0
Rss: 4 kB
Pss: 4 kB
Anonymous: 4 kB
'''
        groups = parse_smaps(text)
        self.assertEqual(groups['/lib/a.so']['Rss'], 30)
        self.assertEqual(groups['/lib/a.so']['Pss'], 17)
        self.assertEqual(groups['[anonymous]']['Anonymous'], 4)
        self.assertEqual(sum(g['Rss'] for g in groups.values()), 34)

    def test_cpu_identity_and_family_memory(self):
        def p(pid, created, cpu):
            return dict(pid=pid, created=created, cpu_seconds=cpu, name='gtk', threads=2,
                        stat_rss_bytes=2**20, rollup_kib=dict(Rss=1024, Pss=512))
        samples = [dict(monotonic=1, processes=[p(1, 1, 20)]),
                   dict(monotonic=3, processes=[p(1, 1, 20.1), p(2, 2, 8)]),
                   dict(monotonic=5, processes=[p(1, 4, 9)])]
        summary = summarize(samples)
        self.assertAlmostEqual(summary['cpu_percent_one_core'], 2.5)
        self.assertEqual(summary['rss_mib'], 1)
        self.assertEqual(summary['pss_mib'], .5)
        self.assertEqual(summary['max_family_processes'], 2)
        self.assertEqual(summary['intervals'], 2)


if __name__ == '__main__':
    unittest.main()
