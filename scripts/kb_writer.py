import json, os, re, shutil, subprocess, sys
from pathlib import Path
from .idutil import slug, fmt_ts, yt_link

LABELS = {
    "ru": {"verdict": {"watch_full": "✅ смотреть целиком", "digest_enough": "📄 хватит выжимки", "skip": "⏭ скип"},
           "takeaways": "💡 Главное:", "applicable": "🛠 Применимое:",
           "on_screen": "📸 Показывают на экране:", "screenshots": "## 📸 Скрины"},
    "en": {"verdict": {"watch_full": "✅ watch in full", "digest_enough": "📄 digest is enough", "skip": "⏭ skip"},
           "takeaways": "💡 Key points:", "applicable": "🛠 Try this:",
           "on_screen": "📸 Shown on screen:", "screenshots": "## 📸 Screenshots"},
}


def _labels(lang: str) -> dict:
    return LABELS["ru"] if str(lang) == "ru" else LABELS["en"]


def build_message(meta: dict, card: dict, url: str, lang: str = "ru") -> str:
    lbl = _labels(lang)
    out = [f"🎬 {meta.get('title') or 'YouTube'}",
           f"   {meta.get('channel') or '?'} · ⏱ {fmt_ts(meta['duration']) if meta.get('duration') else '?'}",
           f"🧭 {lbl['verdict'].get(card.get('verdict'), '')} — {card.get('verdict_ru','')}"]
    if card.get("summary"):
        out.append(f"\n{card['summary']}")
    if card.get("takeaways"):
        out.append("\n" + lbl["takeaways"])
        for t in card["takeaways"]:
            ts = t.get("ts")
            has = isinstance(ts, (int, float))
            out.append(f"  • {t.get('point','')}{(' ['+fmt_ts(ts)+']') if has else ''}{(' → '+yt_link(url,ts)) if has else ''}")
    if card.get("applicable"):
        out.append("\n" + lbl["applicable"])
        out += [f"  • {a}" for a in card["applicable"]]
    if card.get("visual_moments"):
        out.append("\n" + lbl["on_screen"])
        for v in card["visual_moments"]:
            ts = v.get("ts")
            out.append(f"  • [{fmt_ts(ts)}] {v.get('why','')} → {yt_link(url, ts)}")
    if card.get("theme"):
        out.append(f"\n🏷 {card['theme']}")
    return "\n".join(out)


def iter_index(kb_repo: str):
    """Yield parsed cards.jsonl entries, skipping corrupt lines instead of crashing."""
    idx = Path(kb_repo) / "cards.jsonl"
    if not idx.exists():
        return
    for l in idx.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        try:
            yield json.loads(l)
        except Exception:
            sys.stderr.write("[cards.jsonl: skipped corrupt line]\n")


def upsert_index(kb_repo: str, entry: dict) -> None:
    idx = Path(kb_repo) / "cards.jsonl"
    rows = [e for e in iter_index(kb_repo) if e.get("vid") != entry["vid"]]
    rows.append(entry)
    tmp = idx.with_name("cards.jsonl.tmp")
    tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    os.replace(tmp, idx)


def index_entry(kb_repo: str, vid: str):
    for j in iter_index(kb_repo):
        if j.get("vid") == vid:
            return j
    return None


def _existing_file_for_vid(kb_repo: str, vid: str):
    e = index_entry(kb_repo, vid)
    return e.get("file") if e else None


def existing_frames(kb_repo: str, vid: str, card: dict):
    """Rebuild (ts, why, path) from media files already in the KB — for refile/migrate."""
    out = []
    for vm in card.get("visual_moments") or []:
        ts = vm.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        for base in (Path(kb_repo) / "media" / vid, Path(kb_repo) / "youtube" / "media" / vid):
            p = base / f"{int(ts)}.jpg"
            if p.exists():
                out.append((int(ts), vm.get("why", ""), str(p)))
                break
    return out


def write_card(kb_repo, meta, card, url, vid, top, sub, frames, date_str, lang="ru") -> str:
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
    body = build_message(meta, card, url, lang)
    shots = []
    if frames:
        mdir = Path(kb_repo) / "media" / vid
        mdir.mkdir(parents=True, exist_ok=True)
        for ts, why, path in frames:
            dst = mdir / f"{ts}.jpg"
            try:
                if Path(path).resolve() != dst.resolve():
                    shutil.copy(path, dst)
                shots.append(f"![{why}]({os.path.relpath(dst, sub_dir)})\n*[{fmt_ts(ts)}] {why}*")
            except Exception:
                pass
    if shots:
        body += "\n\n" + _labels(lang)["screenshots"] + "\n\n" + "\n\n".join(shots)
    fpath.write_text(fm + body + "\n", encoding="utf-8")
    upsert_index(kb_repo, {"date": date_str, "url": url, "vid": vid, "top": top, "sub": sub,
                           "meta": meta, "card": card, "file": rel})
    return rel


def git_commit(kb_repo, msg, push=True) -> str:
    """Commit all KB changes. Returns: pushed | committed | clean | push_failed | failed."""
    try:
        subprocess.run(["git", "-C", kb_repo, "add", "-A"], check=True, capture_output=True, timeout=30)
        st = subprocess.run(["git", "-C", kb_repo, "status", "--porcelain"],
                            capture_output=True, text=True, timeout=30)
        if not st.stdout.strip():
            return "clean"
        subprocess.run(["git", "-C", kb_repo, "commit", "-q", "-m", msg], check=True, capture_output=True, timeout=30)
    except Exception as e:
        err = e.stderr.decode()[:120] if getattr(e, "stderr", None) else e
        sys.stderr.write(f"[git: {err}]\n")
        return "failed"
    if not push:
        return "committed"
    p = subprocess.run(["git", "-C", kb_repo, "push", "-q"], capture_output=True, timeout=60)
    if p.returncode != 0:
        err = p.stderr.decode() if p.stderr else str(p.returncode)
        # remote URLs can embed tokens (https://<PAT>@github.com/...) — never echo them
        sys.stderr.write(f"[git push: {re.sub(r'://[^@/]+@', '://***@', err)[:120]}]\n")
        return "push_failed"
    return "pushed"
