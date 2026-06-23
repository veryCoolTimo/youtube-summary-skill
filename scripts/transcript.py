import subprocess, sys, tempfile, os
from .idutil import video_id


def get_captions(vid: str):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception as e:
        sys.stderr.write(f"[yt-transcript-api missing: {e}]\n")
        return None, None
    api = YouTubeTranscriptApi()
    for langs in (["ru"], ["en", "en-US", "en-GB"], None):
        try:
            ft = api.fetch(vid, languages=langs) if langs else api.fetch(vid)
            segs = [{"text": getattr(s, "text", ""), "start": float(getattr(s, "start", 0))} for s in ft]
            if segs:
                return segs, (langs[0] if langs else "auto")
        except Exception:
            continue
    try:
        for t in api.list(vid):
            ft = t.fetch()
            segs = [{"text": getattr(s, "text", ""), "start": float(getattr(s, "start", 0))} for s in ft]
            if segs:
                return segs, getattr(t, "language_code", "auto")
    except Exception as e:
        sys.stderr.write(f"[no captions: {e}]\n")
    return None, None


def whisper_transcribe(url: str, model: str = "medium", compute_type: str = "int8"):
    tmp = tempfile.mkdtemp(prefix="yt_audio_")
    audio = os.path.join(tmp, "a.m4a")
    try:
        subprocess.run(["yt-dlp", "--js-runtimes", "node", "-f", "bestaudio[ext=m4a]/bestaudio/18",
                        "-o", audio, "--no-warnings", url], capture_output=True, timeout=600, check=True)
    except Exception as e:
        sys.stderr.write(f"[audio dl fail: {e}]\n")
        return None, None
    if not os.path.exists(audio):
        cands = [f for f in os.listdir(tmp)]
        if not cands:
            return None, None
        audio = os.path.join(tmp, cands[0])
    try:
        from faster_whisper import WhisperModel
        wm = WhisperModel(model, device="cpu", compute_type=compute_type)
        segments, info = wm.transcribe(audio, vad_filter=True)
        segs = [{"text": s.text.strip(), "start": float(s.start)} for s in segments]
        return (segs, info.language) if segs else (None, None)
    except Exception as e:
        sys.stderr.write(f"[whisper fail: {e}]\n")
        return None, None


def get_transcript(url: str, cfg: dict):
    vid = video_id(url)
    segs, lang = get_captions(vid) if vid else (None, None)
    if segs:
        return segs, lang, "captions"
    w = cfg["whisper"]
    segs, lang = whisper_transcribe(url, w["model"], w["compute_type"])
    if segs:
        return segs, lang, "whisper"
    return None, None, "none"
