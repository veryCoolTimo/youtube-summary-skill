import os, subprocess, sys


def get_stream_url(url: str):
    try:
        out = subprocess.run(["yt-dlp", "--js-runtimes", "node",
            "-f", "bv[height<=1080][ext=mp4]/b[height<=720][ext=mp4]/22/18",
            "--skip-download", "-g", "--no-warnings", url],
            capture_output=True, text=True, timeout=120)
        lines = [l for l in out.stdout.strip().splitlines() if l.startswith("http")]
        return lines[-1] if lines else None
    except Exception as e:
        sys.stderr.write(f"[stream url fail: {e}]\n")
        return None


def grab_frame(stream_url: str, ts: float, out_path: str) -> bool:
    try:
        subprocess.run(["ffmpeg", "-ss", str(int(ts)), "-i", stream_url, "-frames:v", "1",
                        "-q:v", "3", "-y", out_path, "-loglevel", "error"],
                       capture_output=True, timeout=60)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def grab_visual_frames(url: str, card: dict, dest_dir: str, limit: int = 3):
    vms = card.get("visual_moments") or []
    if not vms:
        return []
    surl = get_stream_url(url)
    if not surl:
        return []
    os.makedirs(dest_dir, exist_ok=True)
    frames = []
    for vm in vms[:limit]:
        ts = vm.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        p = os.path.join(dest_dir, f"{int(ts)}.jpg")
        if grab_frame(surl, ts, p):
            frames.append((int(ts), vm.get("why", ""), p))
    return frames
