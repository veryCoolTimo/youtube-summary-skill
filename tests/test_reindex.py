import json
from scripts import reindex


def test_reindex_reindexes_every_card(tmp_path, monkeypatch):
    rows = [{"vid": "A" * 11, "meta": {"title": "t"}, "card": {"tldr": "x"}},
            {"vid": "B" * 11, "meta": {"title": "t2"}, "card": {"tldr": "y"}}]
    (tmp_path / "cards.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    seen = []
    monkeypatch.setattr(reindex.vectorize, "index_card",
                        lambda cfg, m, c, v: seen.append(v) or True)
    n = reindex.reindex({"kb_repo": str(tmp_path), "vector": {"enabled": True}})
    assert n == 2 and seen == ["A" * 11, "B" * 11]


def test_reindex_empty_kb(tmp_path):
    assert reindex.reindex({"kb_repo": str(tmp_path), "vector": {"enabled": True}}) == 0


def test_reindex_skips_corrupt_lines(tmp_path, monkeypatch):
    rows = [{"vid": "A" * 11, "meta": {}, "card": {}}]
    (tmp_path / "cards.jsonl").write_text("{corrupt\n" + json.dumps(rows[0]) + "\n")
    monkeypatch.setattr(reindex.vectorize, "index_card", lambda cfg, m, c, v: True)
    assert reindex.reindex({"kb_repo": str(tmp_path), "vector": {"enabled": True}}) == 1
