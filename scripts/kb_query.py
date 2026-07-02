import argparse, itertools, json, re, sys
from pathlib import Path
from . import kb_writer, vectorize
from .config import load_config, validate


def _load_index(cfg) -> dict:
    return {j.get("vid"): j for j in kb_writer.iter_index(cfg["kb_repo"])}


def _hit(cfg, c) -> dict:
    kb = Path(cfg["kb_repo"])
    vid = c.get("vid")
    return {"vid": vid, "title": c.get("meta", {}).get("title"),
            "date": c.get("date"), "top": c.get("top"), "sub": c.get("sub"),
            "file": str(kb / c["file"]) if c.get("file") else None, "url": c.get("url"),
            "tldr": c.get("card", {}).get("tldr"),
            "takeaways": c.get("card", {}).get("takeaways", []),
            "media_dir": str(kb / "media" / (vid or ""))}


def _keyword_vids(by_vid, question) -> list:
    toks = [t for t in re.split(r"\W+", question.lower(), flags=re.UNICODE) if len(t) >= 3]
    if not toks:
        return []
    scored = []
    for vid, c in by_vid.items():
        card, meta = c.get("card", {}), c.get("meta", {})
        text = " ".join([meta.get("title") or "", card.get("tldr") or "",
                         card.get("summary") or "", card.get("theme") or ""] +
                        [t.get("point", "") for t in card.get("takeaways", [])]).lower()
        score = sum(text.count(t) for t in toks)
        if score:
            scored.append((score, vid))
    scored.sort(key=lambda x: -x[0])
    return [v for _, v in scored]


def fetch(cfg, question, n=5, top=None) -> list:
    by_vid = _load_index(cfg)
    vec = []
    if cfg.get("vector", {}).get("enabled"):
        try:
            vec = [h["vid"] for h in vectorize.query(cfg, question, n=n) if h.get("vid")]
        except Exception as e:
            sys.stderr.write(f"[vector search unavailable, keyword-only: {str(e)[:100]}]\n")
    # interleave so exact keyword matches aren't crowded out by n nearest-neighbour hits
    order, seen = [], set()
    for pair in itertools.zip_longest(vec, _keyword_vids(by_vid, question)):
        for vid in pair:
            if vid and vid not in seen:
                seen.add(vid)
                order.append(vid)
    out = []
    for vid in order:
        c = by_vid.get(vid)
        if not c or (top and c.get("top") != top):
            continue
        out.append(_hit(cfg, c))
        if len(out) >= n:
            break
    return out


def recent(cfg, n=10, top=None) -> list:
    rows = [c for c in _load_index(cfg).values() if not top or c.get("top") == top]
    rows.reverse()  # same-date ties: last ingested first
    rows.sort(key=lambda c: c.get("date") or "", reverse=True)
    return [_hit(cfg, c) for c in rows[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--top", help="filter by top-level category")
    ap.add_argument("--recent", type=int, metavar="N", help="list N most recently saved cards instead of searching")
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = validate(load_config(a.config))
    if a.recent is not None:
        out = recent(cfg, a.recent, a.top)
    elif a.question:
        out = fetch(cfg, a.question, a.n, a.top)
    else:
        ap.error("provide a question or --recent N")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
