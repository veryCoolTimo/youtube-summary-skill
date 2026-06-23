import os
from pathlib import Path

_EMBEDDERS = {}
DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def card_text(meta: dict, card: dict) -> str:
    parts = [meta.get("title", ""), card.get("tldr", ""), card.get("summary", "")]
    parts += [t.get("point", "") for t in card.get("takeaways", [])]
    parts += list(card.get("applicable", []))
    return "\n".join(p for p in parts if p)


def _embed(texts, model=DEFAULT_EMBED_MODEL):
    if model not in _EMBEDDERS:
        from fastembed import TextEmbedding
        _EMBEDDERS[model] = TextEmbedding(model_name=model)
    return [list(v) for v in _EMBEDDERS[model].embed(list(texts))]


def _model(cfg):
    return cfg.get("vector", {}).get("embed_model") or DEFAULT_EMBED_MODEL


def _collection(cfg):
    import chromadb
    path = os.path.expanduser(cfg["vector"]["path"])
    Path(path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection("youtube", metadata={"hnsw:space": "cosine"})


def index_card(cfg, meta, card, vid) -> bool:
    if not cfg.get("vector", {}).get("enabled"):
        return False
    col = _collection(cfg)
    try:
        col.delete(where={"vid": vid})
    except Exception:
        pass
    text = card_text(meta, card)
    col.add(ids=[vid], embeddings=_embed([text], _model(cfg)), documents=[text],
            metadatas=[{"vid": vid, "title": meta.get("title", "")}])
    return True


def query(cfg, text, n=5):
    col = _collection(cfg)
    r = col.query(query_embeddings=_embed([text], _model(cfg)), n_results=n)
    out = []
    for i, doc in enumerate(r.get("documents", [[]])[0]):
        md = r.get("metadatas", [[]])[0][i]
        dist = r.get("distances", [[]])[0][i]
        out.append({"vid": md.get("vid"), "text": doc, "distance": dist})
    return out
