"""Test readiness parsing without starting a browser or local server."""
import unittest

import site_visual_smoke as smoke


class SiteVisualSmokeTests(unittest.TestCase):
    def html(self, tables=0, cards=5):
        return '<article class="card fw"></article>' * cards + '<table class="data desktop-table"></table>' * tables

    def test_absent_dataset_is_an_explicit_skip_not_an_invented_table(self):
        result = smoke.inspect_dom(self.html(), False)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["desktop_tables"], 0)
        self.assertIn("skipped", result["desktop_table_assertion"])

    def test_present_dataset_requires_all_three_os_tables(self):
        self.assertEqual(smoke.inspect_dom(self.html(3), True)["status"], "passed")
        self.assertEqual(smoke.inspect_dom(self.html(2), True)["status"], "failed")

    def test_historical_loader_failure_is_not_a_pass(self):
        self.assertEqual(smoke.inspect_dom(self.html(cards=0), False)["status"], "failed")
        self.assertEqual(smoke.inspect_dom(self.html() + '<p class="error">Failed</p>', False)["status"], "failed")

    def test_flags_keep_the_browser_sandbox_enabled(self):
        self.assertIn("--headless", smoke.CHROME_FLAGS)
        self.assertFalse(any("sandbox" in flag for flag in smoke.CHROME_FLAGS))


if __name__ == "__main__":
    unittest.main()
