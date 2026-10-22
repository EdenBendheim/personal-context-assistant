"""Explicitly enabled loopback embeddings; no model pull, proxy or fallback."""
from dataclasses import asdict, dataclass
from http.client import HTTPConnection, HTTPException
import json
from urllib.parse import urlsplit

from .embeddings import normalize_vectors, validate_texts
from .local_model import LocalModelConfig, LocalModelError

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class LocalEmbeddingConfig:
    model: str
    endpoint: str = 'http://127.0.0.1:11434'
    timeout: float = 30
    local_only_confirmed: bool = False

    def __post_init__(self):
        # Share the drafting client's loopback, model-name and timeout rules.
        checked = LocalModelConfig(**asdict(self))
        object.__setattr__(self, 'endpoint', checked.endpoint)


class OllamaEmbeddingProvider:
    def __init__(self, config: LocalEmbeddingConfig):
        if not isinstance(config, LocalEmbeddingConfig):
            raise ValueError('Use validated local embedding settings')
        self.config = config

    def describe(self):
        return dict(backend='ollama_embed', settings=asdict(self.config), truncate=False,
                    identity_note='Requested model/settings; model weights and retrieval quality are not verified')

    def embed(self, texts):
        inputs = validate_texts(texts)
        connection = HTTPConnection('127.0.0.1', urlsplit(self.config.endpoint).port,
                                    timeout=self.config.timeout)
        try:
            payload = dict(model=self.config.model, input=list(inputs), truncate=False, keep_alive='0')
            connection.request('POST', '/api/embed', json.dumps(payload).encode(),
                               {'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise LocalModelError(f'Local embedding model returned HTTP {response.status}; no fallback')
            if response.getheader('Content-Type', '').split(';')[0] != 'application/json':
                raise LocalModelError('Local embedding model returned a non-JSON response')
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise LocalModelError('Local embedding response exceeds the byte budget')
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeError, RecursionError):
                raise LocalModelError('Local embedding model returned invalid JSON') from None
            if not isinstance(result, dict) or result.get('error'):
                raise LocalModelError('Local embedding model returned an invalid or failed result')
            try:
                vectors = normalize_vectors(result.get('embeddings'), len(inputs))
            except ValueError:
                raise LocalModelError('Local embedding model returned malformed vectors') from None
            return [list(vector) for vector in vectors]
        except (OSError, HTTPException):
            raise LocalModelError('Local embedding model unavailable or timed out; no fallback') from None
        finally:
            connection.close()
