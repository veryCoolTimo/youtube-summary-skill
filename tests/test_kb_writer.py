import json
from pathlib import Path
from scripts import kb_writer

CARD = {"verdict": "digest_enough", "verdict_ru": "ок", "tldr": "t", "summary": "s",
        "takeaways": [{"point": "p", "ts": 10}], "applicable": ["a"], "theme": "th",
        "visual_moments": []}
META = {"title": "Some Video", "channel": "Chan", "duration": 60}


def test_upsert_index_no_duplicates(tmp_path):
    kb = str(tmp_path)
    e1 = {"vid": "AAAAAAAAAAA", "url": "u1", "date": "2026-06-23", "meta": META, "card": CARD}
    kb_writer.upsert_index(kb, e1)
    kb_writer.upsert_index(kb, {**e1, "card": {**CARD, "theme": "updated"}})
    lines = (Path(kb) / "cards.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["card"]["theme"] == "updated"


def test_upsert_index_distinct_vids_append(tmp_path):
    kb = str(tmp_path)
    kb_writer.upsert_index(kb, {"vid": "AAAAAAAAAAA", "date": "d", "meta": META, "card": CARD, "url": "u"})
    kb_writer.upsert_index(kb, {"vid": "BBBBBBBBBBB", "date": "d", "meta": META, "card": CARD, "url": "u"})
    lines = (Path(kb) / "cards.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2


def test_write_card_idempotent_path(tmp_path):
    kb = str(tmp_path)
    (Path(kb) / ".git").mkdir()
    p1 = kb_writer.write_card(kb, META, CARD, "https://youtu.be/AAAAAAAAAAA", "AAAAAAAAAAA",
                              "skills", "frontend", frames=[], date_str="2026-06-23")
    p2 = kb_writer.write_card(kb, META, {**CARD, "tldr": "new"}, "https://youtu.be/AAAAAAAAAAA",
                              "AAAAAAAAAAA", "skills", "frontend", frames=[], date_str="2026-06-23")
    assert p1 == p2
    assert p1.startswith("skills/frontend/2026-06-23-")
    lines = (Path(kb) / "cards.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1


def test_reclassify_removes_orphan_file(tmp_path):
    kb = str(tmp_path)
    (Path(kb) / ".git").mkdir()
    p1 = kb_writer.write_card(kb, META, CARD, "https://youtu.be/AAAAAAAAAAA", "AAAAAAAAAAA",
                              "random", "_inbox", frames=[], date_str="2026-06-23")
    p2 = kb_writer.write_card(kb, META, CARD, "https://youtu.be/AAAAAAAAAAA", "AAAAAAAAAAA",
                              "skills", "ai-agents", frames=[], date_str="2026-06-23")
    assert not (Path(kb) / p1).exists()
    assert (Path(kb) / p2).exists()
    assert len((Path(kb) / "cards.jsonl").read_text().strip().splitlines()) == 1
