import re
from pathlib import Path
import yaml

_EXAMPLE = Path(__file__).resolve().parent.parent / "taxonomy.example.yaml"


def load_taxonomy(kb_repo: str) -> dict:
    p = Path(kb_repo) / "taxonomy.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text()) or {}
    tax = yaml.safe_load(_EXAMPLE.read_text())
    p.write_text(yaml.safe_dump(tax, allow_unicode=True, sort_keys=False))
    return tax


def fallback(taxonomy: dict):
    top = "random" if "random" in taxonomy else next(iter(taxonomy), "random")
    return top, "_inbox"


def build_classify_prompt(card: dict, meta: dict, taxonomy: dict) -> str:
    opts = "\n".join(f"{t}: {', '.join(subs or [])}" for t, subs in taxonomy.items())
    return ("Отнеси видео к ОДНОЙ паре top/sub СТРОГО из списка ниже. "
            "Ответь только строкой вида top/sub, без пояснений.\n\n"
            f"СПИСОК:\n{opts}\n\n"
            f"ВИДЕО: {meta.get('title','')} | тема: {card.get('theme','')} | {card.get('tldr','')}")


def _parse_pair(raw: str, taxonomy: dict):
    by_lower = {t.lower(): t for t in taxonomy}
    tops = "|".join(re.escape(t) for t in by_lower)
    # tolerate separators the model may use: "skills/ai-agents", "skills: ai-agents", "skills ai-agents"
    m = re.search(rf"({tops})\b[\s:/]+([\w-]+)", (raw or "").strip().lower())
    return (by_lower[m.group(1)], m.group(2)) if m else (None, None)


def _valid(top: str, sub: str, taxonomy: dict) -> bool:
    return sub in [s.lower() for s in taxonomy.get(top) or []]


def classify(card: dict, meta: dict, taxonomy: dict, override, llm_fn):
    if override and "/" in override:
        top, sub = override.split("/", 1)
        if top in taxonomy:
            return top, re.sub(r"[^\w-]", "-", sub.strip().lower())
    # engine=self puts its pick into the card, so no extra LLM round-trip is needed
    top, sub = _parse_pair(str(card.get("category", "")), taxonomy)
    if top and _valid(top, sub, taxonomy):
        return top, sub
    if llm_fn is None:
        return fallback(taxonomy)
    top, sub = _parse_pair(llm_fn(build_classify_prompt(card, meta, taxonomy)), taxonomy)
    if not top:
        return fallback(taxonomy)
    if not _valid(top, sub, taxonomy):
        return top, "_inbox"
    return top, sub
