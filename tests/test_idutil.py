from scripts.idutil import video_id, slug, fmt_ts, yt_link


def test_video_id_variants():
    assert video_id("https://www.youtube.com/watch?v=fVPCbCH_c1c") == "fVPCbCH_c1c"
    assert video_id("https://youtu.be/fVPCbCH_c1c") == "fVPCbCH_c1c"
    assert video_id("https://youtube.com/shorts/fVPCbCH_c1c") == "fVPCbCH_c1c"
    assert video_id("fVPCbCH_c1c") == "fVPCbCH_c1c"
    assert video_id("not a url") is None


def test_slug():
    assert slug("Turn Claude Code into a Design GENIUS!") == "turn-claude-code-into-a-design-genius"
    assert slug("Привет Мир") == "привет-мир"
    assert slug("") == "video"


def test_fmt_ts():
    assert fmt_ts(75) == "1:15"
    assert fmt_ts(3725) == "1:02:05"


def test_yt_link():
    assert yt_link("https://youtu.be/fVPCbCH_c1c", 111) == "https://youtu.be/fVPCbCH_c1c?t=111"
