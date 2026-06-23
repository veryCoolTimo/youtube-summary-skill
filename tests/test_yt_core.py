from pathlib import Path
from scripts import yt_core


def test_process_video_end_to_end(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    (kb / ".git").mkdir(parents=True)
    (kb / "taxonomy.yaml").write_text("skills: [frontend]\nreviews: [tools]\nstartup: [ideas]\nrandom: [misc]\n")
    card = {"verdict": "watch_full", "verdict_ru": "огонь", "tldr": "t", "summary": "s",
            "takeaways": [{"point": "p", "ts": 3}], "applicable": ["a"], "theme": "frontend", "visual_moments": []}
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "Vid", "channel": "C", "duration": 10})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: ([{"text": "hi", "start": 0}], "en", "captions"))
    monkeypatch.setattr(yt_core.distill, "distill", lambda *a, **k: dict(card))
    monkeypatch.setattr(yt_core.frames, "grab_visual_frames", lambda *a, **k: [])
    monkeypatch.setattr(yt_core.kb_writer, "git_commit", lambda *a, **k: "committed")
    cfg = {"kb_repo": str(kb), "distill": {"engine": "openrouter", "openrouter_models": ["m"]},
           "whisper": {"model": "medium", "compute_type": "int8"},
           "vector": {"enabled": False}, "frames": {"max_per_video": 3}}
    r = yt_core.process_video("https://youtu.be/AAAAAAAAAAA", cfg, key="k", override="skills/frontend", today="2026-06-23")
    assert r["status"] == "ok" and r["top"] == "skills" and r["sub"] == "frontend"
    assert (kb / r["file"]).exists()
    yt_core.process_video("https://youtu.be/AAAAAAAAAAA", cfg, key="k", override="skills/frontend", today="2026-06-23")
    assert len((kb / "cards.jsonl").read_text().strip().splitlines()) == 1


def test_process_video_no_transcript_fails(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    (kb / ".git").mkdir(parents=True)
    (kb / "taxonomy.yaml").write_text("skills: [frontend]\nreviews: []\nstartup: []\nrandom: [misc]\n")
    monkeypatch.setattr(yt_core, "get_meta", lambda u: {"title": "V", "channel": "C", "duration": 0})
    monkeypatch.setattr(yt_core.transcript, "get_transcript", lambda u, cfg: (None, None, "none"))
    cfg = {"kb_repo": str(kb), "distill": {"engine": "openrouter", "openrouter_models": ["m"]},
           "whisper": {"model": "medium", "compute_type": "int8"}, "vector": {"enabled": False}, "frames": {"max_per_video": 3}}
    r = yt_core.process_video("https://youtu.be/BBBBBBBBBBB", cfg, key="k", today="2026-06-23")
    assert r["status"] == "failed" and "transcript" in r["reason"]
