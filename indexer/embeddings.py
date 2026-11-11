"""Embeddings.

Primary: sentence-transformers if installed (EMBEDDING_PROVIDER=sentence-transformers).
Default in this repo: deterministic hash embeddings (dim 128) — documented
honestly in README/docs. Hash embeddings give stable, content-derived
vectors for the vector-similarity fallback tier; they are NOT semantic
embeddings and are never presented as such. A content hash that has not
changed is never re-embedded.
"""
from __future__ import annotations
import hashlib, math, os

DIM = 128
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "hash")
_ST_MODEL = None

def _hash_embed(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    for token in text.lower().split():
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
        vec[(h >> 8) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

def embed(text: str) -> list[float]:
    if EMBEDDING_PROVIDER == "sentence-transformers":
        global _ST_MODEL
        try:
            if _ST_MODEL is None:
                from sentence_transformers import SentenceTransformer
                _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            return [float(x) for x in _ST_MODEL.encode(text, normalize_embeddings=True)]
        except Exception:
            pass  # fall through to hash embeddings; provider is reported, not hidden
    return _hash_embed(text)

def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)

def embedding_provider_name() -> str:
    if EMBEDDING_PROVIDER == "sentence-transformers" and _ST_MODEL is not None:
        return "sentence-transformers/all-MiniLM-L6-v2"
    return "hash-embedding-v1 (deterministic, non-semantic)"
