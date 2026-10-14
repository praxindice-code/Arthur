"""Build ArthurAI's playable place without overwriting an open Studio file.

The older BayesGuard place is only a geometry/template source. The editable
Luau files in test-range/ are the source of truth for all four scripts.
"""

from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "BayesGuard-Test-Range.rbxlx"
OUTPUT = ROOT / "ArthurAI-Test-Range.rbxlx"
SCRIPTS = {
    "MovementDetector": "MovementDetector.lua",
    "RangeLiveObserver": "RangeLiveObserver.server.lua",
    "BayesGuardRange": "BayesGuardRange.server.lua",
    "RangeExperiments": "RangeExperiments.server.lua",
}


def replace_source(place: str, name: str, source: str) -> str:
    marker = f'<string name="Name">{name}</string>'
    if place.count(marker) != 1:
        raise ValueError(f"expected exactly one {name} script")
    name_at = place.index(marker)
    item_at = place.rfind('<Item class="', 0, name_at)
    opener = '<ProtectedString name="Source"><![CDATA['
    source_at = place.rfind(opener, item_at, name_at)
    if source_at < 0:
        raise ValueError(f"missing CDATA source for {name}")
    source_at += len(opener)
    source_end = place.index(']]></ProtectedString>', source_at)
    if source_end > name_at or "]]>" in source:
        raise ValueError(f"unsafe source boundary for {name}")
    return place[:source_at] + source + place[source_end:]


def insert_experiments(place: str, source: str) -> str:
    if '<string name="Name">RangeExperiments</string>' in place:
        return replace_source(place, "RangeExperiments", source)
    marker = '<string name="Name">BayesGuardRange</string>'
    name_at = place.index(marker)
    after_item = place.index('</Item>', name_at) + len('</Item>')
    referent = 'RBX7A4DF6DD9BA64A54A9113149EA0B1004'
    if referent in place or "]]>" in source:
        raise ValueError("duplicate referent or unsafe CDATA content")
    item = (
        '\n\t\t<Item class="Script" referent="' + referent + '">\n'
        '\t\t\t<Properties>\n'
        '\t\t\t\t<ProtectedString name="Source"><![CDATA[' + source + ']]></ProtectedString>\n'
        '\t\t\t\t<bool name="Disabled">false</bool>\n'
        '\t\t\t\t<token name="RunContext">1</token>\n'
        '\t\t\t\t<string name="Name">RangeExperiments</string>\n'
        '\t\t\t</Properties>\n'
        '\t\t</Item>'
    )
    return place[:after_item] + item + place[after_item:]


def main() -> None:
    place = TEMPLATE.read_text(encoding="utf-8")
    for name in ("MovementDetector", "RangeLiveObserver", "BayesGuardRange"):
        source = (ROOT / "test-range" / SCRIPTS[name]).read_text(encoding="utf-8")
        place = replace_source(place, name, source)
    experiments = (ROOT / "test-range" / SCRIPTS["RangeExperiments"]).read_text(encoding="utf-8")
    place = insert_experiments(place, experiments)
    ET.fromstring(place)
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing place: {OUTPUT}")
    OUTPUT.write_text(place, encoding="utf-8", newline="\n")
    print(f"Built {OUTPUT}")


if __name__ == "__main__":
    main()
