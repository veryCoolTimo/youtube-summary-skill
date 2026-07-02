import sys
import types
from types import SimpleNamespace
from scripts import transcript

CFG = {"whisper": {"model": "medium", "compute_type": "int8"}}


def test_get_transcript_prefers_captions(monkeypatch):
    monkeypatch.setattr(transcript, "get_captions",
                        lambda vid, priority=None: ([{"text": "hi", "start": 0}], "en"))
    called = {"whisper": False}
    monkeypatch.setattr(transcript, "whisper_transcribe",
                        lambda *a, **k: called.__setitem__("whisper", True) or (None, None))
    segs, lang, src = transcript.get_transcript("https://youtu.be/fVPCbCH_c1c", CFG)
    assert src == "captions" and lang == "en" and called["whisper"] is False


def test_get_transcript_falls_back_to_whisper(monkeypatch):
    monkeypatch.setattr(transcript, "get_captions", lambda vid, priority=None: (None, None))
    monkeypatch.setattr(transcript, "whisper_transcribe",
                        lambda url, model, compute_type: ([{"text": "spoken", "start": 1}], "ru"))
    segs, lang, src = transcript.get_transcript("https://youtu.be/fVPCbCH_c1c", CFG)
    assert src == "whisper" and segs[0]["text"] == "spoken"


def test_get_transcript_none(monkeypatch):
    monkeypatch.setattr(transcript, "get_captions", lambda vid, priority=None: (None, None))
    monkeypatch.setattr(transcript, "whisper_transcribe", lambda *a, **k: (None, None))
    segs, lang, src = transcript.get_transcript("https://youtu.be/fVPCbCH_c1c", CFG)
    assert src == "none" and segs is None


def test_caption_language_priority_from_config(monkeypatch):
    captured = {}

    def fake_captions(vid, priority=None):
        captured["priority"] = priority
        return [{"text": "x", "start": 0}], "de"

    monkeypatch.setattr(transcript, "get_captions", fake_captions)
    cfg = {**CFG, "captions": {"languages": ["de", "en"]}}
    transcript.get_transcript("https://youtu.be/fVPCbCH_c1c", cfg)
    assert captured["priority"] == ["de", "en"]


def test_whisper_cleans_up_tempdir(monkeypatch, tmp_path):
    workdir = tmp_path / "aud"
    workdir.mkdir()
    monkeypatch.setattr(transcript.tempfile, "mkdtemp", lambda prefix="": str(workdir))

    def fake_run(cmd, **kw):
        (workdir / "a.m4a").write_bytes(b"x")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(transcript.subprocess, "run", fake_run)
    fw = types.ModuleType("faster_whisper")

    class WM:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, vad_filter=True):
            return [SimpleNamespace(text="hi", start=0.0)], SimpleNamespace(language="en")

    fw.WhisperModel = WM
    monkeypatch.setitem(sys.modules, "faster_whisper", fw)
    segs, lang = transcript.whisper_transcribe("url")
    assert segs[0]["text"] == "hi" and lang == "en"
    assert not workdir.exists()
