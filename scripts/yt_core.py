import argparse, datetime as dt, json, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from . import transcript, distill, classify, frames, kb_writer, vectorize
from .idutil import video_id
from .config import load_config, env, validate


def _meta_via_ytdlp(url: str) -> dict:
    try:
        out = subprocess.run(["yt-dlp", "--js-runtimes", "node", "--skip-download", "--no-warnings",
                              "--print", "%(title)s\t%(channel)s\t%(duration)s", url],
                             capture_output=True, text=True, timeout=60)
        parts = out.stdout.strip().split("\t")
        if parts and parts[0]:
            dur = parts[2] if len(parts) > 2 else "0"
            try:
                dur_i = int(float(dur))
            except ValueError:
                dur_i = 0
            return {"title": parts[0], "channel": parts[1] if len(parts) > 1 else "",
                    "duration": dur_i}
    except Exception as e:
        sys.stderr.write(f"[ytdlp meta fail: {e}]\n")
    return {"title": "", "channel": "", "duration": 0}


def get_meta(url: str) -> dict:
    vid = video_id(url) or ""
    try:
        o = f"https://www.youtube.com/oembed?url=https://youtu.be/{vid}&format=json"
        with urllib.request.urlopen(o, timeout=15) as r:
            j = json.loads(r.read().decode())
        if j.get("title"):
            return {"title": j["title"], "channel": j.get("author_name", ""), "duration": 0}
    except Exception as e:
        sys.stderr.write(f"[oembed warn: {e}]\n")
    return _meta_via_ytdlp(url)


def _self_prompt_dir(vid: str) -> Path:
    return Path(tempfile.gettempdir()) / f"ytself_{vid}"


def _emit_self_prompt(meta, segs, tax, lang, vid) -> str:
    opts = "\n".join(f"{t}: {', '.join(subs or [])}" for t, subs in tax.items())
    sys_p = (distill.sys_prompt(lang) +
             f'\nДополнительно добавь в JSON поле "category" вида "top/sub", выбирая СТРОГО из:\n{opts}')
    d = _self_prompt_dir(vid)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "prompt.txt"
    p.write_text("=== SYSTEM ===\n" + sys_p + "\n\n=== USER ===\n" + distill.build_user_prompt(meta, segs),
                 encoding="utf-8")
    return str(p)


def _refile(cfg, entry, override, today) -> dict:
    """Move an already-saved card to another category without re-distilling."""
    tax = classify.load_taxonomy(cfg["kb_repo"])
    meta, card = entry.get("meta", {}), entry.get("card", {})
    vid = entry["vid"]
    top, sub = classify.classify(card, meta, tax, override, llm_fn=None)
    url = entry.get("url", f"https://youtu.be/{vid}")
    fr = kb_writer.existing_frames(cfg["kb_repo"], vid, card)
    rel = kb_writer.write_card(cfg["kb_repo"], meta, card, url, vid, top, sub, fr,
                               entry.get("date") or today)
    vectorize.index_card(cfg, meta, card, vid)
    return {"status": "refiled", "vid": vid, "file": rel, "top": top, "sub": sub,
            "title": meta.get("title")}


def process_video(url, cfg, key, override=None, self_fn=None, today=None, force=False, card_file=None):
    vid = video_id(url)
    if not vid:
        return {"status": "failed", "reason": f"bad url: {url}"}
    url = f"https://youtu.be/{vid}"  # canonical: never pass raw user input to subprocesses
    today = today or dt.date.today().isoformat()
    if override:
        tax = classify.load_taxonomy(cfg["kb_repo"])
        top = override.split("/", 1)[0] if "/" in override else ""
        if top not in tax:
            return {"status": "failed", "vid": vid,
                    "reason": f"unknown category '{override}'; tops: {', '.join(tax)}"}
    existing = kb_writer.index_entry(cfg["kb_repo"], vid)
    if existing and not force and not card_file:
        if override:
            return _refile(cfg, existing, override, today)
        return {"status": "exists", "vid": vid, "file": existing.get("file"),
                "top": existing.get("top"), "sub": existing.get("sub"),
                "title": existing.get("meta", {}).get("title"),
                "hint": "already saved; use --force to re-process"}
    meta = get_meta(url)
    engine = cfg["distill"]["engine"]
    lang = cfg["distill"].get("language", "ru")
    tax = classify.load_taxonomy(cfg["kb_repo"])
    if card_file:
        try:
            card = distill.parse_card(Path(card_file).read_text(encoding="utf-8"))
        except Exception as e:
            return {"status": "failed", "vid": vid, "reason": f"card-file: {str(e)[:120]}"}
        card["_engine"] = "self"
        source = "self-card"
        if not meta.get("duration"):
            meta["duration"] = _meta_via_ytdlp(url).get("duration", 0)
    else:
        segs, _tlang, source = transcript.get_transcript(url, cfg)
        if not segs:
            return {"status": "failed", "vid": vid, "reason": "no transcript (captions+whisper failed)"}
        if not meta.get("duration"):
            meta["duration"] = int(segs[-1]["start"]) + 5
        if engine == "self" and not self_fn:
            return {"status": "need_card", "vid": vid, "title": meta.get("title"),
                    "prompt_file": _emit_self_prompt(meta, segs, tax, lang, vid),
                    "next": "write the card JSON to a file, then rerun the same command with --card-file <path>"}
        try:
            card = distill.distill(meta, segs, cfg, key, self_fn=self_fn)
        except Exception as e:
            return {"status": "failed", "vid": vid, "reason": f"distill: {str(e)[:120]}"}
    try:
        top, sub = classify.classify(card, meta, tax, override, llm_fn=distill.classify_chat_fn(cfg, key))
    except Exception as e:
        sys.stderr.write(f"[classify failed, using _inbox: {str(e)[:120]}]\n")
        top, sub = classify.fallback(tax)
    fr, fdir = [], None
    if card.get("visual_moments"):
        fdir = tempfile.mkdtemp(prefix="ytf_")
        fr = frames.grab_visual_frames(url, card, fdir, cfg.get("frames", {}).get("max_per_video", 3))
    rel = kb_writer.write_card(cfg["kb_repo"], meta, card, url, vid, top, sub, fr, today)
    if fdir:
        shutil.rmtree(fdir, ignore_errors=True)
    vectorize.index_card(cfg, meta, card, vid)
    if card_file:
        shutil.rmtree(_self_prompt_dir(vid), ignore_errors=True)
    return {"status": "ok", "vid": vid, "file": rel, "top": top, "sub": sub,
            "source": source, "engine": card.get("_engine"),
            "title": meta.get("title"), "tldr": card.get("tldr")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--engine", choices=["openrouter", "local", "self"])
    ap.add_argument("--category")
    ap.add_argument("--config")
    ap.add_argument("--force", action="store_true", help="re-process even if the video is already saved")
    ap.add_argument("--card-file", help="engine=self: path to the card JSON written from the emitted prompt")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    cfg = validate(load_config(a.config))
    if a.engine:
        cfg["distill"]["engine"] = a.engine
    if a.card_file:
        if len(a.urls) > 1:
            ap.error("--card-file works with a single url")
        cfg["distill"]["engine"] = "self"
    key = env("OPENROUTER_API_KEY", cfg.get("env_file"))
    results = []
    for url in a.urls:
        try:
            r = process_video(url, cfg, key, override=a.category, force=a.force, card_file=a.card_file)
        except Exception as e:
            r = {"status": "failed", "vid": video_id(url), "reason": str(e)[:200]}
        results.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    done = [r for r in results if r.get("status") in ("ok", "refiled")]
    if done:
        if len(done) == 1:
            msg = f"Add YT note: {(done[0].get('title') or done[0].get('vid') or '')[:60]}"
        else:
            msg = f"Add {len(done)} YT notes"
        st = kb_writer.git_commit(cfg["kb_repo"], msg, push=not a.no_push)
    else:
        st = "skipped"
    print(json.dumps({"git": st, "videos": len(done)}))


if __name__ == "__main__":
    main()
