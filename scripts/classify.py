import re
from pathlib import Path
import yaml

TOPS = ["skills", "reviews", "startup", "random"]
_EXAMPLE = Path(__file__).resolve().parent.parent / "taxonomy.example.yaml"


def load_taxonomy(kb_repo: str) -> dict:
    p = Path(kb_repo) / "taxonomy.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text()) or {}
    tax = yaml.safe_load(_EXAMPLE.read_text())
    p.write_text(yaml.safe_dump(tax, allow_unicode=True, sort_keys=False))
    return tax


def build_classify_prompt(card: dict, meta: dict, taxonomy: dict) -> str:
    opts = "\n".join(f"{t}: {', '.join(subs)}" for t, subs in taxonomy.items())
    return ("Отнеси видео к ОДНОЙ паре top/sub СТРОГО из списка ниже. "
            "Ответь только строкой вида top/sub, без пояснений.\n\n"
            f"СПИСОК:\n{opts}\n\n"
            f"ВИДЕО: {meta.get('title','')} | тема: {card.get('theme','')} | {card.get('tldr','')}")


def classify(card: dict, meta: dict, taxonomy: dict, override, llm_fn):
    if override and "/" in override:
        top, sub = override.split("/", 1)
        if top in TOPS:
            return top, re.sub(r"[^\w-]", "-", sub.strip().lower())
    raw = (llm_fn(build_classify_prompt(card, meta, taxonomy)) or "").strip().lower()
    # tolerate separators the model may use: "skills/ai-agents", "skills: ai-agents", "skills ai-agents"
    m = re.search(r"(" + "|".join(TOPS) + r")\b[\s:/]+([\w-]+)", raw)
    if not m:
        return "random", "_inbox"
    top, sub = m.group(1), m.group(2)
    if sub not in [s.lower() for s in taxonomy.get(top, [])]:
        return top, "_inbox"
    return top, sub
