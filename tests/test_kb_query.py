import json
from scripts import kb_query


def _kb(tmp_path):
    rows = [
        {"vid": "AAAAAAAAAAA", "date": "2026-06-01", "top": "skills", "sub": "ai-agents",
         "file": "skills/ai-agents/a.md", "url": "u1",
         "meta": {"title": "MCP servers deep dive"},
         "card": {"tldr": "how to build MCP servers", "takeaways": [{"point": "use stdio", "ts": 5}]}},
        {"vid": "BBBBBBBBBBB", "date": "2026-06-20", "top": "startup", "sub": "ideas",
         "file": "startup/ideas/b.md", "url": "u2",
         "meta": {"title": "Founder story"},
         "card": {"tldr": "bootstrapping a saas", "takeaways": []}},
        {"vid": "CCCCCCCCCCC", "date": "2026-06-20", "top": "reviews", "sub": "tools",
         "file": "reviews/tools/c.md", "url": "u3",
         "meta": {"title": "Editor review"},
         "card": {"tldr": "a code editor walkthrough", "takeaways": []}},
    ]
    (tmp_path / "cards.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return {"kb_repo": str(tmp_path), "vector": {"enabled": False}}


def test_fetch_keyword_search_without_vector(tmp_path):
    hits = kb_query.fetch(_kb(tmp_path), "MCP", n=5)
    assert [h["vid"] for h in hits] == ["AAAAAAAAAAA"]


def test_fetch_returns_absolute_paths(tmp_path):
    h = kb_query.fetch(_kb(tmp_path), "MCP")[0]
    assert h["file"] == str(tmp_path / "skills/ai-agents/a.md")
    assert h["media_dir"] == str(tmp_path / "media/AAAAAAAAAAA")


def test_keyword_hits_not_crowded_out_by_vector(tmp_path, monkeypatch):
    cfg = _kb(tmp_path)
    cfg["vector"]["enabled"] = True
    monkeypatch.setattr(kb_query.vectorize, "query",
                        lambda c, q, n=5: [{"vid": "BBBBBBBBBBB"}, {"vid": "CCCCCCCCCCC"}])
    hits = kb_query.fetch(cfg, "MCP", n=2)
    assert "AAAAAAAAAAA" in [h["vid"] for h in hits]


def test_corrupt_index_line_is_tolerated(tmp_path):
    cfg = _kb(tmp_path)
    p = tmp_path / "cards.jsonl"
    p.write_text("{corrupt\n" + p.read_text())
    hits = kb_query.fetch(cfg, "MCP")
    assert [h["vid"] for h in hits] == ["AAAAAAAAAAA"]


def test_recent_newest_first_with_insertion_tiebreak(tmp_path):
    hits = kb_query.recent(_kb(tmp_path), n=2)
    assert [h["vid"] for h in hits] == ["CCCCCCCCCCC", "BBBBBBBBBBB"]


def test_top_filter(tmp_path):
    hits = kb_query.recent(_kb(tmp_path), n=5, top="skills")
    assert [h["vid"] for h in hits] == ["AAAAAAAAAAA"]
