from scripts.config import env, load_config


def test_env_from_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text("OPENROUTER_API_KEY=sk-test-123\nOTHER=x\n")
    assert env("OPENROUTER_API_KEY", str(f)) == "sk-test-123"


def test_env_from_os(monkeypatch):
    monkeypatch.setenv("FOO_BAR", "y")
    assert env("FOO_BAR", "/nonexistent") == "y"


def test_load_config_defaults():
    cfg = load_config()
    assert cfg["distill"]["engine"] == "openrouter"
    assert cfg["whisper"]["model"] in ("medium", "large-v3", "small")
