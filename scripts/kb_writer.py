import json, os, shutil, subprocess, sys
from pathlib import Path
from .idutil import slug, fmt_ts, yt_link

VERDICT_EMOJI = {"watch_full": "✅ смотреть целиком", "digest_enough": "📄 хватит выжимки", "skip": "⏭ скип"}


def build_message(meta: dict, card: dict, url: str) -> str:
    out = [f"🎬 {meta.get('title') or 'YouTube'}",
           f"   {meta.get('channel') or '?'} · ⏱ {fmt_ts(meta['duration']) if meta.get('duration') else '?'}",
           f"🧭 {VERDICT_EMOJI.get(card.get('verdict'), '')} — {card.get('verdict_ru','')}"]
    if card.get("summary"):
        out.append(f"\n{card['summary']}")
    if card.get("takeaways"):
        out.append("\n💡 Главное:")
        for t in card["takeaways"]:
            ts = t.get("ts")
            has = isinstance(ts, (int, float))
            out.append(f"  • {t.get('point','')}{(' ['+fmt_ts(ts)+']') if has else ''}{(' → '+yt_link(url,ts)) if has else ''}")
    if card.get("applicable"):
        out.append("\n🛠 Применимое:")
        out += [f"  • {a}" for a in card["applicable"]]
    if card.get("visual_moments"):
        out.append("\n📸 Показывают на экране:")
        for v in card["visual_moments"]:
            ts = v.get("ts")
            out.append(f"  • [{fmt_ts(ts)}] {v.get('why','')} → {yt_link(url, ts)}")
    if card.get("theme"):
        out.append(f"\n🏷 {card['theme']}")
    return "\n".join(out)


def upsert_index(kb_repo: str, entry: dict) -> None:
    idx = Path(kb_repo) / "cards.jsonl"
    rows = []
    if idx.exists():
        for l in idx.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            try:
                if json.loads(l).get("vid") != entry["vid"]:
                    rows.append(l)
            except Exception:
                rows.append(l)
    rows.append(json.dumps(entry, ensure_ascii=False))
    idx.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _existing_file_for_vid(kb_repo: str, vid: str):
    idx = Path(kb_repo) / "cards.jsonl"
    if not idx.exists():
        return None
    for l in idx.read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(l)
            if j.get("vid") == vid:
                return j.get("file")
        except Exception:
            continue
    return None


def write_card(kb_repo, meta, card, url, vid, top, sub, frames, date_str) -> str:
    sub_dir = Path(kb_repo) / top / sub
    sub_dir.mkdir(parents=True, exist_ok=True)
    rel = f"{top}/{sub}/{date_str}-{slug(meta.get('title') or vid)}.md"
    fpath = Path(kb_repo) / rel
    # if this video was previously stored at a different path (re-classified), drop the orphan
    old = _existing_file_for_vid(kb_repo, vid)
    if old and old != rel:
        oldp = Path(kb_repo) / old
        if oldp.exists():
            oldp.unlink()
    fm = (f"---\ntitle: {json.dumps(meta.get('title',''), ensure_ascii=False)}\n"
          f"channel: {json.dumps(meta.get('channel',''), ensure_ascii=False)}\n"
          f"url: {url}\nvideo_id: {vid}\ndate: {date_str}\n"
          f"verdict: {card.get('verdict','')}\ntop: {top}\nsub: {sub}\n"
          f"theme: {json.dumps(card.get('theme',''), ensure_ascii=False)}\n---\n\n")
    body = build_message(meta, card, url)
    shots = []
    if frames:
        mdir = Path(kb_repo) / "media" / vid
        mdir.mkdir(parents=True, exist_ok=True)
        for ts, why, path in frames:
            dst = mdir / f"{ts}.jpg"
            try:
                shutil.copy(path, dst)
                shots.append(f"![{why}]({os.path.relpath(dst, sub_dir)})\n*[{fmt_ts(ts)}] {why}*")
            except Exception:
                pass
    if shots:
        body += "\n\n## 📸 Скрины\n\n" + "\n\n".join(shots)
    fpath.write_text(fm + body + "\n", encoding="utf-8")
    upsert_index(kb_repo, {"date": date_str, "url": url, "vid": vid, "top": top, "sub": sub,
                           "meta": meta, "card": card, "file": rel})
    return rel


def git_commit(kb_repo, msg, push=True) -> str:
    try:
        subprocess.run(["git", "-C", kb_repo, "add", "-A"], check=True, capture_output=True, timeout=30)
        subprocess.run(["git", "-C", kb_repo, "commit", "-q", "-m", msg], check=True, capture_output=True, timeout=30)
        if push:
            subprocess.run(["git", "-C", kb_repo, "push", "-q"], capture_output=True, timeout=60)
        return "committed"
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"[git: {e.stderr.decode()[:120] if e.stderr else e}]\n")
        return "uncommitted"
