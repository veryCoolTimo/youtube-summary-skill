import pytest
import scripts.config as config_module
from scripts.config import env, load_config, validate


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


def test_validate_rejects_placeholder_kb_repo():
    with pytest.raises(SystemExit):
        validate({"kb_repo": "/path/to/your/knowledge-base"})


def test_validate_rejects_missing_dir(tmp_path):
    with pytest.raises(SystemExit):
        validate({"kb_repo": str(tmp_path / "nope")})


def test_validate_expands_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "kb").mkdir()
    cfg = {"kb_repo": "~/kb"}
    assert validate(cfg) is cfg
    assert cfg["kb_repo"] == str(tmp_path / "kb")


def test_validate_empty_kb_repo_defaults_to_local_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "ROOT", tmp_path)
    cfg = {"kb_repo": ""}
    validate(cfg)
    assert cfg["kb_repo"] == str(tmp_path / "knowledge-base")
    assert (tmp_path / "knowledge-base").is_dir()
