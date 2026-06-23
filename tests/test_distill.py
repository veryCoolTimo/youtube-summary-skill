import json
from scripts import distill

SEGS = [{"text": "hello world", "start": 5}, {"text": "this MCP does X", "start": 12}]
META = {"title": "Test", "channel": "Chan", "duration": 60}
CARD = {"verdict": "digest_enough", "verdict_ru": "ок", "tldr": "t", "summary": "s",
        "takeaways": [{"point": "p", "ts": 12}], "applicable": ["a"],
        "theme": "th", "visual_moments": []}


def test_parse_card_strips_markdown_fence():
    raw = "```json\n" + json.dumps(CARD) + "\n```"
    assert distill.parse_card(raw)["verdict"] == "digest_enough"


def test_build_user_prompt_includes_timestamps():
    p = distill.build_user_prompt(META, SEGS)
    assert "[5]" in p and "this MCP does X" in p and "Test" in p


def test_distill_self_engine_calls_callback():
    captured = {}

    def fake_self(sys_p, usr_p):
        captured["sys"] = sys_p
        return json.dumps(CARD)

    cfg = {"distill": {"engine": "self"}}
    out = distill.distill(META, SEGS, cfg, key="", self_fn=fake_self)
    assert out["theme"] == "th"
    assert out["_engine"] == "self"
    assert "JSON" in captured["sys"]


def test_openrouter_fallback_skips_failing_model(monkeypatch):
    def fake_chat(model, messages, key, timeout=120):
        if model == "free":
            raise RuntimeError("429 Too Many Requests")
        return "ok-from-" + model
    monkeypatch.setattr(distill, "_openrouter_chat", fake_chat)
    model, raw = distill.openrouter_chat_fallback(["free", "paid"], [], "k")
    assert model == "paid" and raw == "ok-from-paid"


def test_distill_openrouter_uses_first_model(monkeypatch):
    calls = []

    def fake_chat(model, messages, key, timeout=120):
        calls.append(model)
        return json.dumps(CARD)

    monkeypatch.setattr(distill, "_openrouter_chat", fake_chat)
    cfg = {"distill": {"engine": "openrouter", "openrouter_models": ["m1", "m2"]}}
    out = distill.distill(META, SEGS, cfg, key="k")
    assert calls == ["m1"]
    assert out["_engine"] == "openrouter:m1"
