import argparse, datetime as dt, json, sys
from pathlib import Path
from . import classify, kb_writer, vectorize, distill
from .config import load_config, env, validate


def dedup_old(rows):
    by_vid = {}
    for r in rows:
        vid = r.get("vid")
        if not vid:
            continue
        prev = by_vid.get(vid)
        if prev is None or (r.get("card") and len(json.dumps(r["card"])) >= len(json.dumps(prev.get("card") or {}))):
            by_vid[vid] = r
    return list(by_vid.values())


def migrate(cfg, key, old_index_path, today):
    kb = cfg["kb_repo"]
    rows = [json.loads(l) for l in Path(old_index_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = dedup_old(rows)
    tax = classify.load_taxonomy(kb)
    llm = distill.classify_chat_fn(cfg, key)

    res = {"migrated": 0, "skipped": 0, "by_folder": {}}
    for r in rows:
        vid, meta, card = r.get("vid"), r.get("meta", {}), r.get("card", {})
        url = r.get("url", f"https://youtu.be/{vid}")
        if not vid or not card:
            res["skipped"] += 1
            continue
        try:
            top, sub = classify.classify(card, meta, tax, None, llm)
        except Exception:
            top, sub = classify.fallback(tax)
        frames = kb_writer.existing_frames(kb, vid, card)
        date = (r.get("date") or today)
        kb_writer.write_card(kb, meta, card, url, vid, top, sub, frames, date,
                             lang=cfg["distill"].get("language", "ru"))
        try:
            vectorize.index_card(cfg, meta, card, vid)
        except Exception as e:
            sys.stderr.write(f"[vector skip {vid}: {str(e)[:100]}]\n")
        res["migrated"] += 1
        res["by_folder"][f"{top}/{sub}"] = res["by_folder"].get(f"{top}/{sub}", 0) + 1
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-index", required=True, help="path to the old flat cards.jsonl to migrate")
    ap.add_argument("--config")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    a = ap.parse_args()
    cfg = validate(load_config(a.config))
    key = env("OPENROUTER_API_KEY", cfg.get("env_file"))
    print(json.dumps(migrate(cfg, key, a.old_index, a.today), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
