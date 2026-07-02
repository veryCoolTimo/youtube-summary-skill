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


def test_llm_none_goes_inbox():
    top, sub = classify.classify(CARD, META, TAX, None, llm_fn=None)
    assert (top, sub) == ("random", "_inbox")


def test_custom_taxonomy_tops_are_recognized():
    tax = {"career": ["interviews"], "random": ["misc"]}
    top, sub = classify.classify(CARD, META, tax, None, llm_fn=lambda p: "career/interviews")
    assert (top, sub) == ("career", "interviews")


def test_custom_taxonomy_override_accepted():
    tax = {"career": ["interviews"], "random": ["misc"]}
    top, sub = classify.classify(CARD, META, tax, "career/offers", llm_fn=lambda p: "random/misc")
    assert (top, sub) == ("career", "offers")


def test_card_category_hint_wins_without_llm():
    card = {**CARD, "category": "skills/ai-agents"}

    def boom(p):
        raise AssertionError("llm must not be called when card has a valid category")

    top, sub = classify.classify(card, META, TAX, None, llm_fn=boom)
    assert (top, sub) == ("skills", "ai-agents")


def test_invalid_card_category_falls_to_llm():
    card = {**CARD, "category": "skills/bogus"}
    top, sub = classify.classify(card, META, TAX, None, llm_fn=lambda p: "reviews/tools")
    assert (top, sub) == ("reviews", "tools")


def test_empty_taxonomy_subs_no_crash():
    tax = {"skills": None, "random": ["misc"]}
    top, sub = classify.classify(CARD, META, tax, None, llm_fn=lambda p: "skills/anything")
    assert (top, sub) == ("skills", "_inbox")


def test_llm_garbage_custom_taxonomy_falls_to_first_top():
    tax = {"career": ["x"]}
    top, sub = classify.classify(CARD, META, tax, None, llm_fn=lambda p: "junk")
    assert (top, sub) == ("career", "_inbox")


def test_taxonomy_tops_case_insensitive():
    tax = {"Skills": ["Frontend"], "random": ["misc"]}
    top, sub = classify.classify(CARD, META, tax, None, llm_fn=lambda p: "skills/frontend")
    assert (top, sub) == ("Skills", "frontend")
