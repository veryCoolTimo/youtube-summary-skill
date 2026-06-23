from scripts import transcript

CFG = {"whisper": {"model": "medium", "compute_type": "int8"}}


def test_get_transcript_prefers_captions(monkeypatch):
    monkeypatch.setattr(transcript, "get_captions",
                        lambda vid: ([{"text": "hi", "start": 0}], "en"))
    called = {"whisper": False}
    monkeypatch.setattr(transcript, "whisper_transcribe",
                        lambda *a, **k: called.__setitem__("whisper", True) or (None, None))
    segs, lang, src = transcript.get_transcript("https://youtu.be/fVPCbCH_c1c", CFG)
    assert src == "captions" and lang == "en" and called["whisper"] is False


def test_get_transcript_falls_back_to_whisper(monkeypatch):
    monkeypatch.setattr(transcript, "get_captions", lambda vid: (None, None))
    monkeypatch.setattr(transcript, "whisper_transcribe",
                        lambda url, model, compute_type: ([{"text": "spoken", "start": 1}], "ru"))
    segs, lang, src = transcript.get_transcript("https://youtu.be/fVPCbCH_c1c", CFG)
    assert src == "whisper" and segs[0]["text"] == "spoken"


def test_get_transcript_none(monkeypatch):
    monkeypatch.setattr(transcript, "get_captions", lambda vid: (None, None))
    monkeypatch.setattr(transcript, "whisper_transcribe", lambda *a, **k: (None, None))
    segs, lang, src = transcript.get_transcript("https://youtu.be/fVPCbCH_c1c", CFG)
    assert src == "none" and segs is None
