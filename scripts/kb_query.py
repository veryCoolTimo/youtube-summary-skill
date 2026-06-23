import argparse, json
from pathlib import Path
from . import vectorize
from .config import load_config


def fetch(cfg, question, n=5):
    hits = vectorize.query(cfg, question, n=n)
    idx = Path(cfg["kb_repo"]) / "cards.jsonl"
    by_vid = {}
    if idx.exists():
        for l in idx.read_text(encoding="utf-8").splitlines():
            if l.strip():
                j = json.loads(l)
                by_vid[j.get("vid")] = j
    out = []
    for h in hits:
        c = by_vid.get(h["vid"])
        if not c:
            continue
        out.append({"vid": h["vid"], "title": c.get("meta", {}).get("title"),
                    "file": c.get("file"), "url": c.get("url"),
                    "tldr": c.get("card", {}).get("tldr"),
                    "takeaways": c.get("card", {}).get("takeaways", []),
                    "media_dir": f"media/{h['vid']}"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--config")
    a = ap.parse_args()
    print(json.dumps(fetch(load_config(a.config), a.question, a.n), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
