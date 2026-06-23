from scripts import vectorize

CARD = {"tldr": "agents tldr", "summary": "about ai agents", "takeaways": [{"point": "use mcp"}], "applicable": ["try x"]}
META = {"title": "Agents"}


def test_card_text_concats():
    t = vectorize.card_text(META, CARD)
    assert "agents tldr" in t and "use mcp" in t and "try x" in t


def test_index_and_query_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(vectorize, "_embed", lambda texts, model=None: [[float(len(t) % 7), 1.0, 0.0, 0.0] for t in texts])
    cfg = {"vector": {"enabled": True, "path": str(tmp_path / "chroma"), "embed_model": "stub"}}
    assert vectorize.index_card(cfg, META, CARD, "AAAAAAAAAAA") is True
    vectorize.index_card(cfg, META, CARD, "AAAAAAAAAAA")
    res = vectorize.query(cfg, "ai agents", n=5)
    vids = [r["vid"] for r in res]
    assert vids.count("AAAAAAAAAAA") == 1
