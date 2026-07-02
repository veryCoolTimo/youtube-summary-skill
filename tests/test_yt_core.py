import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from scripts import yt_core, kb_writer

CARD = {"verdict": "watch_full", "verdict_ru": "огонь", "tldr": "t", "summary": "s",
        "takeaways": [{"point": "p", "ts": 3}], "applicable": ["a"], "theme": "frontend",
        "visual_moments": []}


def _cfg(kb, engine="openrouter"):
    return {"kb_repo": str(kb),
            "distill": {"engine": engine, "openrouter_models": ["m"], "local_model": "lm"},
            "whisper": {"model": "medium", "compute_type": "int8"},
            "vector": {"enabled": False}, "frames": {"max_per_video": 3}}


def _kb(tmp_path):
    kb = tmp_path / "kb"
    (kb / ".git").mkdir(parents=True)
    (kb / "taxonomy.yaml").write_text("skills: [frontend]\nreviews: [tools]\nstartup: [ideas]\nrandom: [misc]\n")
    return kb


def _seed(kb, vid="AAAAAAAAAAA", top="random", sub="_inbox"):
    return kb_writer.write_card(str(kb), {"title": "Vid", "channel": "C", "duration": 10}, dict(CARD),
                                f"https://youtu.be/{vid}", vid, top, sub, [], "2026-06-23")


def _boom(*a, **k):
    raise AssertionError("must not be called")


def test_process_video_end_to_end(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: ([{"text": "hi", "start": 0}], "en", "captions"))
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(CARD))
    monkeypatch.setattr(yt_core.frames, "grab_visual_frames", lambda *a, **k: [])
    cfg = _cfg(kb)
    r = yt_core.process_video("https://youtu.be/AAAAAAAAAAA", cfg, key="k", override="skills/frontend", today="2026-06-23")
    assert r["status"] == "ok" and r["top"] == "skills" and r["sub"] == "frontend"
    assert r["title"] == "Vid" and r["tldr"] == "t"
    assert (kb / r["file"]).exists()
    yt_core.process_video("https://youtu.be/AAAAAAAAAAA", cfg, key="k", override="skills/frontend", today="2026-06-23")
    assert len((kb / "cards.jsonl").read_text().strip().splitlines()) == 1


def test_process_video_no_transcript_fails(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "V", "channel": "C", "duration": 0})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: (None, None, "none"))
    r = yt_core.process_video("https://youtu.be/BBBBBBBBBBB", _cfg(kb), key="k", today="2026-06-23")
    assert r["status"] == "failed" and "transcript" in r["reason"]


def test_existing_video_returns_exists_without_reprocessing(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    _seed(kb)
    monkeypatch.setattr(yt_core.transcript, "get_transcript", _boom)
    monkeypatch.setattr(yt_core.distill, "distill", _boom)
    r = yt_core.process_video("https://youtu.be/AAAAAAAAAAA", _cfg(kb), key="k", today="2026-06-24")
    assert r["status"] == "exists" and r["file"] and r["title"] == "Vid"


def test_force_reprocesses_existing(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    _seed(kb)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: ([{"text": "hi", "start": 0}], "en", "captions"))
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(CARD))
    r = yt_core.process_video("https://youtu.be/AAAAAAAAAAA", _cfg(kb), key="k",
                              override="skills/frontend", today="2026-06-24", force=True)
    assert r["status"] == "ok"


def test_refile_existing_with_override_skips_distill(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    old = _seed(kb)
    monkeypatch.setattr(yt_core.transcript, "get_transcript", _boom)
    monkeypatch.setattr(yt_core.distill, "distill", _boom)
    r = yt_core.process_video("https://youtu.be/AAAAAAAAAAA", _cfg(kb), key="k",
                              override="skills/frontend", today="2026-06-24")
    assert r["status"] == "refiled" and (r["top"], r["sub"]) == ("skills", "frontend")
    assert not (kb / old).exists() and (kb / r["file"]).exists()


def test_self_engine_emits_prompt_file(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript",
                        lambda u, cfg: ([{"text": "unique-token", "start": 0}], "en", "captions"))
    r = yt_core.process_video("https://youtu.be/CCCCCCCCCCC", _cfg(kb, engine="self"), key="")
    assert r["status"] == "need_card"
    text = Path(r["prompt_file"]).read_text(encoding="utf-8")
    assert "unique-token" in text and "frontend" in text and "category" in text


def test_self_engine_resumes_from_card_file(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core.transcript, "get_transcript", _boom)
    monkeypatch.setattr(yt_core.distill, "distill", _boom)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    cf = tmp_path / "card.json"
    cf.write_text(json.dumps({**CARD, "category": "skills/frontend"}, ensure_ascii=False), encoding="utf-8")
    r = yt_core.process_video("https://youtu.be/CCCCCCCCCCC", _cfg(kb, engine="self"), key="", card_file=str(cf))
    assert r["status"] == "ok" and (r["top"], r["sub"]) == ("skills", "frontend")
    assert r["engine"] == "self"


def test_local_engine_classifies_via_ollama(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: ([{"text": "hi", "start": 0}], "en", "captions"))
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(CARD))
    monkeypatch.setattr(yt_core.distill, "openrouter_chat_fallback", _boom)
    monkeypatch.setattr(yt_core.distill, "_ollama_chat", lambda model, msgs, timeout=600: "skills/frontend")
    r = yt_core.process_video("https://youtu.be/DDDDDDDDDDD", _cfg(kb, engine="local"), key="")
    assert r["status"] == "ok" and (r["top"], r["sub"]) == ("skills", "frontend")


def test_process_video_does_not_commit(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: ([{"text": "hi", "start": 0}], "en", "captions"))
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(CARD))
    monkeypatch.setattr(yt_core.kb_writer, "git_commit", _boom)
    r = yt_core.process_video("https://youtu.be/EEEEEEEEEEE", _cfg(kb), key="k", override="skills/frontend")
    assert r["status"] == "ok"


def test_main_commits_once_per_batch(tmp_path, monkeypatch, capsys):
    kb = _kb(tmp_path)
    calls = []
    monkeypatch.setattr(yt_core, "load_config", lambda p: _cfg(kb))
    monkeypatch.setattr(yt_core, "process_video",
                        lambda url, cfg, key, override=None, force=False, card_file=None:
                        {"status": "ok", "vid": url[-11:], "title": "T"})
    monkeypatch.setattr(yt_core.kb_writer, "git_commit",
                        lambda repo, msg, push=True: calls.append((msg, push)) or "pushed")
    monkeypatch.setattr(sys, "argv", ["yt_core", "https://youtu.be/AAAAAAAAAAA", "https://youtu.be/BBBBBBBBBBB"])
    yt_core.main()
    out = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert len(calls) == 1
    assert out[-1]["git"] == "pushed" and out[-1]["videos"] == 2


def test_main_skips_commit_when_nothing_saved(tmp_path, monkeypatch, capsys):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "load_config", lambda p: _cfg(kb))
    monkeypatch.setattr(yt_core, "process_video",
                        lambda url, cfg, key, override=None, force=False, card_file=None:
                        {"status": "exists", "vid": url[-11:]})
    monkeypatch.setattr(yt_core.kb_writer, "git_commit", _boom)
    monkeypatch.setattr(sys, "argv", ["yt_core", "https://youtu.be/AAAAAAAAAAA"])
    yt_core.main()
    out = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert out[0]["status"] == "exists"
    assert out[-1]["git"] == "skipped" and out[-1]["videos"] == 0


def test_main_batch_survives_exception(tmp_path, monkeypatch, capsys):
    kb = _kb(tmp_path)
    calls = []

    def pv(url, cfg, key, override=None, force=False, card_file=None):
        if "AAAA" in url:
            raise RuntimeError("chroma exploded")
        return {"status": "ok", "vid": url[-11:], "title": "T"}

    monkeypatch.setattr(yt_core, "load_config", lambda p: _cfg(kb))
    monkeypatch.setattr(yt_core, "process_video", pv)
    monkeypatch.setattr(yt_core.kb_writer, "git_commit",
                        lambda repo, msg, push=True: calls.append(msg) or "pushed")
    monkeypatch.setattr(sys, "argv", ["yt_core", "https://youtu.be/AAAAAAAAAAA", "https://youtu.be/BBBBBBBBBBB"])
    yt_core.main()
    out = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert out[0]["status"] == "failed" and "chroma" in out[0]["reason"]
    assert out[1]["status"] == "ok"
    assert len(calls) == 1 and out[-1]["git"] == "pushed"


def test_refile_with_unknown_top_fails_loudly(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    old = _seed(kb)
    monkeypatch.setattr(yt_core.transcript, "get_transcript", _boom)
    monkeypatch.setattr(yt_core.distill, "distill", _boom)
    r = yt_core.process_video("https://youtu.be/AAAAAAAAAAA", _cfg(kb), key="k",
                              override="skils/frontend", today="2026-06-24")
    assert r["status"] == "failed" and "skils" in r["reason"]
    assert (kb / old).exists()  # the correctly-filed card is untouched


def test_refile_preserves_screenshots(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    vid = "AAAAAAAAAAA"
    src = tmp_path / "5.jpg"
    src.write_bytes(b"jpg")
    card = {**CARD, "visual_moments": [{"ts": 5, "why": "demo"}]}
    kb_writer.write_card(str(kb), {"title": "Vid", "channel": "C", "duration": 10}, card,
                         f"https://youtu.be/{vid}", vid, "random", "_inbox",
                         [(5, "demo", str(src))], "2026-06-23")
    assert (kb / "media" / vid / "5.jpg").exists()
    monkeypatch.setattr(yt_core.distill, "distill", _boom)
    r = yt_core.process_video(f"https://youtu.be/{vid}", _cfg(kb), key="k", override="skills/frontend")
    assert r["status"] == "refiled"
    assert "Скрины" in (kb / r["file"]).read_text(encoding="utf-8")


def test_card_file_invalid_json_fails_gracefully(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    cf = tmp_path / "card.json"
    cf.write_text("this is not json")
    r = yt_core.process_video("https://youtu.be/CCCCCCCCCCC", _cfg(kb, engine="self"), key="", card_file=str(cf))
    assert r["status"] == "failed" and "card" in r["reason"]


def test_url_canonicalized_before_pipeline(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    seen = {}

    def fake_tr(u, cfg):
        seen["url"] = u
        return [{"text": "hi", "start": 0}], "en", "captions"

    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", fake_tr)
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(CARD))
    yt_core.process_video("https://www.youtube.com/watch?v=GGGGGGGGGGG&list=x --exec=evil",
                          _cfg(kb), key="k", override="skills/frontend")
    assert seen["url"] == "https://youtu.be/GGGGGGGGGGG"


def test_classify_exception_falls_back_to_taxonomy_top(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    (kb / ".git").mkdir(parents=True)
    (kb / "taxonomy.yaml").write_text("career: [x]\n")

    def raise_rt(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: ([{"text": "hi", "start": 0}], "en", "captions"))
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(CARD))
    monkeypatch.setattr(yt_core.classify, "classify", raise_rt)
    r = yt_core.process_video("https://youtu.be/HHHHHHHHHHH", _cfg(kb), key="k")
    assert (r["top"], r["sub"]) == ("career", "_inbox")


def test_self_prompt_dir_cleaned_after_resume(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript",
                        lambda u, cfg: ([{"text": "x", "start": 0}], "en", "captions"))
    r1 = yt_core.process_video("https://youtu.be/CCCCCCCCCCC", _cfg(kb, engine="self"), key="")
    pdir = Path(r1["prompt_file"]).parent
    assert pdir.exists()
    cf = tmp_path / "card.json"
    cf.write_text(json.dumps({**CARD, "category": "skills/frontend"}, ensure_ascii=False), encoding="utf-8")
    r2 = yt_core.process_video("https://youtu.be/CCCCCCCCCCC", _cfg(kb, engine="self"), key="", card_file=str(cf))
    assert r2["status"] == "ok"
    assert not pdir.exists()


def test_frames_tempdir_removed(tmp_path, monkeypatch):
    kb = _kb(tmp_path)
    fdir = tmp_path / "frames_tmp"
    monkeypatch.setattr(tempfile, "mkdtemp", lambda prefix="": fdir.mkdir() or str(fdir))
    card = {**CARD, "visual_moments": [{"ts": 1, "why": "demo"}]}
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: ([{"text": "hi", "start": 0}], "en", "captions"))
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(card))
    monkeypatch.setattr(yt_core.frames, "grab_visual_frames", lambda *a, **k: [])
    r = yt_core.process_video("https://youtu.be/FFFFFFFFFFF", _cfg(kb), key="k", override="skills/frontend")
    assert r["status"] == "ok"
    assert not fdir.exists()


def test_meta_via_ytdlp_parses_float_duration(monkeypatch):
    monkeypatch.setattr(yt_core.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout="Title\tChan\t123.4\n"))
    m = yt_core._meta_via_ytdlp("u")
    assert m["duration"] == 123
