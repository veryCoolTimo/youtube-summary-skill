import os
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(key: str, env_file: str | None = None) -> str:
    if env_file:
        try:
            for line in Path(env_file).read_text().splitlines():
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return os.environ.get(key, "")


def validate(cfg: dict) -> dict:
    kb = os.path.expanduser(str(cfg.get("kb_repo") or ""))
    if not kb or kb == "/path/to/your/knowledge-base":
        raise SystemExit("config error: set kb_repo in config.yaml (path to your local knowledge-base git clone)")
    if not Path(kb).is_dir():
        raise SystemExit(f"config error: kb_repo does not exist: {kb}")
    cfg["kb_repo"] = kb
    return cfg


def load_config(path: str | None = None) -> dict:
    cfg = yaml.safe_load((ROOT / "config.example.yaml").read_text())
    user = Path(path) if path else ROOT / "config.yaml"
    if user.exists():
        u = yaml.safe_load(user.read_text()) or {}
        _deep_merge(cfg, u)
    return cfg


def _deep_merge(base: dict, over: dict):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
