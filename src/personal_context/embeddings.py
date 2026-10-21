"""Validated embedding contract; no model, network access or learned encoder here."""
import math
from typing import Protocol

MAX_TEXTS = 129
MAX_DIMENSIONS = 4096


class EmbeddingProvider(Protocol):
    def describe(self) -> dict: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def validate_texts(texts):
    if (not isinstance(texts, (list, tuple)) or not 1 <= len(texts) <= MAX_TEXTS
            or any(not isinstance(text, str) or not text.strip() for text in texts)):
        raise ValueError('Embed 1-129 nonempty text strings')
    if any(len(text.encode('utf-8')) > 4096 for text in texts):
        raise ValueError('Embedding text exceeds the 4,096-byte limit')
    if sum(len(text.encode('utf-8')) for text in texts) > 262144:
        raise ValueError('Embedding input exceeds the 262,144-byte total limit')
    return tuple(texts)


def normalize_vectors(vectors, count):
    if (type(count) is not int or not 1 <= count <= MAX_TEXTS
            or not isinstance(vectors, (list, tuple)) or len(vectors) != count):
        raise ValueError('Embedding response count must match the inputs')
    result = []
    dimension = None
    for vector in vectors:
        if not isinstance(vector, (list, tuple)) or not 1 <= len(vector) <= MAX_DIMENSIONS:
            raise ValueError('Embedding dimension must be 1-4096')
        if dimension is None:
            dimension = len(vector)
        if len(vector) != dimension:
            raise ValueError('Embedding dimensions must match across every input')
        if any(type(value) not in (int, float) for value in vector):
            raise ValueError('Embedding coordinates must be finite numbers')
        try:
            values = tuple(float(value) for value in vector)
            norm = math.hypot(*values)
        except (OverflowError, ValueError):
            raise ValueError('Embedding coordinates must be finite numbers') from None
        if not all(math.isfinite(value) for value in values) or not math.isfinite(norm) or norm == 0:
            raise ValueError('Embedding vectors must be finite and nonzero')
        result.append(tuple(value / norm for value in values))
    return tuple(result)


def embed_validated(provider: EmbeddingProvider, texts):
    snapshot = validate_texts(texts)
    return normalize_vectors(provider.embed(list(snapshot)), len(snapshot))


def cosine(left, right):
    """Cosine for vectors already validated/normalized by this module."""
    if len(left) != len(right):
        raise ValueError('Cosine dimensions differ')
    return max(-1., min(1., math.fsum(a*b for a, b in zip(left, right))))
