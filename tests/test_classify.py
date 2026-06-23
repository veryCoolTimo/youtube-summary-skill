from scripts import classify

TAX = {"skills": ["frontend", "ai-agents"], "reviews": ["tools"],
       "startup": ["ideas"], "random": ["misc"]}
CARD = {"theme": "AI agents", "summary": "about building agents", "tldr": "agents"}
META = {"title": "Build agents", "channel": "x"}


def test_override_wins():
    top, sub = classify.classify(CARD, META, TAX, "skills/frontend", llm_fn=lambda p: "random/misc")
    assert (top, sub) == ("skills", "frontend")


def test_override_invalid_top_falls_to_llm():
    top, sub = classify.classify(CARD, META, TAX, "bogus/x", llm_fn=lambda p: "skills/ai-agents")
    assert (top, sub) == ("skills", "ai-agents")


def test_llm_pick_must_be_in_taxonomy():
    top, sub = classify.classify(CARD, META, TAX, None, llm_fn=lambda p: "skills/ai-agents")
    assert (top, sub) == ("skills", "ai-agents")


def test_llm_colon_separator_is_parsed():
    top, sub = classify.classify(CARD, META, TAX, None, llm_fn=lambda p: "skills: ai-agents")
    assert (top, sub) == ("skills", "ai-agents")


def test_llm_nofit_goes_to_inbox():
    top, sub = classify.classify(CARD, META, TAX, None, llm_fn=lambda p: "skills/nonexistent")
    assert sub == "_inbox" and top == "skills"


def test_llm_bad_top_goes_random_inbox():
    top, sub = classify.classify(CARD, META, TAX, None, llm_fn=lambda p: "garbage")
    assert (top, sub) == ("random", "_inbox")
