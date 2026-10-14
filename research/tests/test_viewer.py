import json
import unittest

from bayesguard.viewer import render_viewer


class ViewerTests(unittest.TestCase):
    def test_html_contains_traces_and_assets(self):
        html = render_viewer(seed=42, sessions=4)
        self.assertNotIn("/* BAYESGUARD_CSS */", html)
        self.assertNotIn("/* BAYESGUARD_JS */", html)
        self.assertIn('id="risk-plot"', html)
        raw = html.split('<script id="bg-data" type="application/json">', 1)[1].split(
            "</script>", 1)[0]
        data = json.loads(raw)
        self.assertEqual(len(data["scenarios"]), 4)
        self.assertIsNotNone(data["scenarios"][1]["attack_start"])
        self.assertEqual(len(data["scenarios"][0]["events"][0]["posterior"]), 5)


if __name__ == "__main__":
    unittest.main()
