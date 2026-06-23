import argparse, datetime as dt, json, subprocess, sys, urllib.request
from . import transcript, distill, classify, frames, kb_writer, vectorize
from .idutil import video_id
from .config import load_config, env


def _meta_via_ytdlp(url: str) -> dict:
    try:
        out = subprocess.run(["yt-dlp", "--js-runtimes", "node", "--skip-download", "--no-warnings",
                              "--print", "%(title)s\t%(channel)s\t%(duration)s", url],
                             capture_output=True, text=True, timeout=60)
        parts = out.stdout.strip().split("\t")
        if parts and parts[0]:
            dur = parts[2] if len(parts) > 2 else "0"
            return {"title": parts[0], "channel": parts[1] if len(parts) > 1 else "",
                    "duration": int(dur) if dur.isdigit() else 0}
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


def process_video(url, cfg, key, override=None, self_fn=None, today=None):
    vid = video_id(url)
    if not vid:
        return {"status": "failed", "reason": f"bad url: {url}"}
    today = today or dt.date.today().isoformat()
    meta = get_meta(url)
    segs, lang, source = transcript.get_transcript(url, cfg)
    if not segs:
        return {"status": "failed", "vid": vid, "reason": "no transcript (captions+whisper failed)"}
    if not meta.get("duration"):
        meta["duration"] = int(segs[-1]["start"]) + 5
    try:
        card = distill.distill(meta, segs, cfg, key, self_fn=self_fn)
    except Exception as e:
        return {"status": "failed", "vid": vid, "reason": f"distill: {str(e)[:120]}"}
    tax = classify.load_taxonomy(cfg["kb_repo"])

    def _llm(prompt):
        _, raw = distill.openrouter_chat_fallback(cfg["distill"]["openrouter_models"],
                                                  [{"role": "user", "content": prompt}], key)
        return raw

    try:
        top, sub = classify.classify(card, meta, tax, override, llm_fn=_llm)
    except Exception as e:
        sys.stderr.write(f"[classify failed, using _inbox: {str(e)[:120]}]\n")
        top, sub = "random", "_inbox"
    fr = []
    if card.get("visual_moments"):
        import tempfile
        fr = frames.grab_visual_frames(url, card, tempfile.mkdtemp(prefix="ytf_"),
                                       cfg.get("frames", {}).get("max_per_video", 3))
    rel = kb_writer.write_card(cfg["kb_repo"], meta, card, url, vid, top, sub, fr, today)
    vectorize.index_card(cfg, meta, card, vid)
    kb_writer.git_commit(cfg["kb_repo"], f"Add YT note: {(meta.get('title') or vid)[:60]}",
                         push=cfg.get("_push", True))
    return {"status": "ok", "vid": vid, "file": rel, "top": top, "sub": sub,
            "source": source, "engine": card.get("_engine")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--engine", choices=["openrouter", "local", "self"])
    ap.add_argument("--category")
    ap.add_argument("--config")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.engine:
        cfg["distill"]["engine"] = a.engine
    cfg["_push"] = not a.no_push
    key = env("OPENROUTER_API_KEY", cfg.get("env_file"))
    for url in a.urls:
        r = process_video(url, cfg, key, override=a.category)
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
