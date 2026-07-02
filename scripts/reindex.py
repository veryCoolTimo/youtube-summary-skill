import argparse, json
from . import kb_writer, vectorize
from .config import load_config, validate


def reindex(cfg) -> int:
    """Rebuild the vector index from cards.jsonl (e.g. on a new machine). No LLM calls."""
    vectorize.reset(cfg)  # drop embeddings of deleted cards
    n = 0
    for j in kb_writer.iter_index(cfg["kb_repo"]):
        if not j.get("vid"):
            continue
        if vectorize.index_card(cfg, j.get("meta", {}), j.get("card", {}), j["vid"]):
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = validate(load_config(a.config))
    if not cfg.get("vector", {}).get("enabled"):
        print(json.dumps({"indexed": 0, "note": "vector.enabled is false in config"}))
        return
    print(json.dumps({"indexed": reindex(cfg)}))


if __name__ == "__main__":
    main()
