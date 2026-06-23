from scripts.migrate_kb import dedup_old


def test_dedup_keeps_one_per_vid_last_wins():
    rows = [
        {"vid": "A", "card": {"theme": "old"}},
        {"vid": "B", "card": {"theme": "x"}},
        {"vid": "A", "card": {"theme": "new-and-longer-card-body"}},
    ]
    out = dedup_old(rows)
    assert len(out) == 2
    a = [r for r in out if r["vid"] == "A"][0]
    assert a["card"]["theme"] == "new-and-longer-card-body"


def test_dedup_prefers_nonempty_card():
    rows = [
        {"vid": "A", "card": {"theme": "real"}},
        {"vid": "A", "card": {}},
    ]
    out = dedup_old(rows)
    assert out[0]["card"]["theme"] == "real"
