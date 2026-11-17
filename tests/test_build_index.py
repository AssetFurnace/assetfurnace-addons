import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_index as bi  # noqa: E402


def entry(addon_id, **extra):
    return {"id": addon_id, "name": addon_id.title(), "repo": "https://github.com/AssetFurnace/x.git",
            "commit": "a" * 40, "author": {"name": "X"}, "summary": "A thing.", **extra}


def write(folder, data):
    (folder / f"{data['id']}.json").write_text(json.dumps(data), encoding="utf-8")


def test_entries_are_combined_and_sorted_by_id(tmp_path):
    write(tmp_path, entry("zebra"))
    write(tmp_path, entry("apple", runs="cloud"))
    entries, problems = bi.build_index(tmp_path)
    assert problems == []
    assert [e["id"] for e in entries] == ["apple", "zebra"]
    assert entries[0]["runs"] == "cloud"


def test_a_bad_entry_blocks_the_whole_list(tmp_path):
    write(tmp_path, entry("good"))
    (tmp_path / "bad.json").write_text(json.dumps({**entry("bad"), "commit": "main"}), encoding="utf-8")
    entries, problems = bi.build_index(tmp_path)
    assert any("bad.json" in p and "40-character" in p for p in problems)


def test_main_writes_nothing_when_something_fails(tmp_path):
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    out = tmp_path / "index.json"
    assert bi.main(["--addons", str(tmp_path), "--out", str(out)]) == 1
    assert not out.exists()


def test_main_writes_the_list_the_app_can_read(tmp_path):
    write(tmp_path, entry("pedestal"))
    out = tmp_path / "index.json"
    assert bi.main(["--addons", str(tmp_path), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))[0]["id"] == "pedestal"
