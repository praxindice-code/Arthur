"""Keep the editable Luau sources and playable Roblox place in sync."""

import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "MovementDetector": "MovementDetector.lua",
    "RangeLiveObserver": "RangeLiveObserver.server.lua",
    "BayesGuardRange": "BayesGuardRange.server.lua",
    "RangeExperiments": "RangeExperiments.server.lua",
}


class TestRangePlace(unittest.TestCase):
    def test_embedded_scripts_match_editable_sources(self):
        place = ET.parse(ROOT / "ArthurAI-Test-Range.rbxlx")
        embedded = {}
        for item in place.iter("Item"):
            if item.get("class") not in {"Script", "ModuleScript"}:
                continue
            properties = item.find("Properties")
            if properties is None:
                continue
            name = properties.find("string[@name='Name']")
            source = properties.find("ProtectedString[@name='Source']")
            if name is not None and source is not None:
                embedded[name.text] = source.text
        for name, filename in SOURCES.items():
            with self.subTest(name=name):
                expected = (ROOT / "test-range" / filename).read_text(encoding="utf-8")
                self.assertEqual(embedded[name].replace("\r\n", "\n"), expected.replace("\r\n", "\n"))

    def test_range_has_fourteen_distinct_scenarios(self):
        source = (ROOT / "test-range" / "BayesGuardRange.server.lua").read_text(encoding="utf-8")
        names = re.findall(r'\bname = "([^"]+)", expected = ', source)
        self.assertEqual(len(names), 14)
        self.assertEqual(len(set(names)), 14)
        self.assertIn("Actor isolation", names)
        self.assertIn("Review cooldown", names)


if __name__ == "__main__":
    unittest.main()
