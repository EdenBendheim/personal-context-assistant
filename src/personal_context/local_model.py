"""Opt-in, bounded loopback Ollama chat client; no pulls, proxies or redirects."""
from copy import deepcopy
from dataclasses import asdict,dataclass
from http.client import HTTPConnection,HTTPException
import json
import math
import re
from urllib.parse import urlsplit

from .generation_format import PROMPTS,PROMPT_VERSION,SCHEMA,parse_proposal,prompt_messages


class LocalModelError(ValueError): pass


@dataclass(frozen=True)
class LocalModelConfig:
    model: str
    endpoint: str = 'http://127.0.0.1:11434'
    timeout: float = 30
    max_tokens: int = 1024
    seed: int = 29
    local_only_confirmed: bool = False
    expected_digest: str | None = None
    prompt_version: str = PROMPT_VERSION
    response_format: str = 'union_schema'

    def __post_init__(self):
        if (not isinstance(self.model,str) or not re.fullmatch(r'[A-Za-z0-9_./:-]{1,100}',self.model)
                or 'cloud' in self.model.casefold()):raise ValueError('Choose an explicitly named local model, not a cloud model')
        try:
            url=urlsplit(self.endpoint)
            valid=(url.scheme=='http' and url.hostname=='127.0.0.1' and url.port is not None
                and 1<=url.port<=65535 and not url.username and not url.password
                and not url.query and not url.fragment and url.path in ('','/'))
        except (ValueError,TypeError,AttributeError):valid=False
        if not valid:raise ValueError('Use http://127.0.0.1:PORT with no credentials, path or query')
        object.__setattr__(self,'endpoint',self.endpoint.rstrip('/'))
        if (type(self.timeout) not in (int,float) or not math.isfinite(self.timeout) or not 1<=self.timeout<=60
                or type(self.max_tokens) is not int or not 64<=self.max_tokens<=2048
                or type(self.seed) is not int or not 0<=self.seed<2**31):raise ValueError('Invalid local inference bounds')
        if self.local_only_confirmed is not True:
            raise ValueError('Confirm Ollama runs with cloud disabled before enabling local inference')
        if self.expected_digest is not None and (not isinstance(self.expected_digest, str)
                or re.fullmatch('[0-9a-f]{64}', self.expected_digest) is None):
            raise ValueError('Expected model digest must be a lowercase SHA-256')
        if not isinstance(self.prompt_version, str) or self.prompt_version not in PROMPTS:
            raise ValueError('Unknown drafting prompt version')
        if self.response_format not in ('union_schema', 'prompt_only'):
            raise ValueError('Unknown drafting response format')


class OllamaProvider:
    def __init__(self,config:LocalModelConfig):
        if not isinstance(config,LocalModelConfig):raise ValueError('Use validated local model settings')
        self.config=config
        from .local_identity import ModelIdentityGuard
        self.identity = ModelIdentityGuard(config, 'completion')

    def describe(self):
        result = dict(backend='ollama_chat',prompt_version=self.config.prompt_version,
            response_format=self.config.response_format,settings=asdict(self.config),
            identity_note='Requested model/settings, not a served-weight attestation or semantic validation')
        if self.config.expected_digest is not None:
            result['model_identity'] = self.identity.capture()
        return result

    def generate(self,packet):
        schema = SCHEMA if self.config.response_format == 'union_schema' else None
        return parse_proposal(self._chat(prompt_messages(packet, version=self.config.prompt_version), schema=schema))

    def _chat(self, messages, *, schema):
        # Conservatively bound prompt bytes, not an estimated tokenizer count.
        if sum(len(m['content'].encode()) for m in messages)>6000:
            raise LocalModelError('Prompt exceeds local 6,000-byte budget; reduce retrieval limit/history')
        self.identity.capture()
        payload=dict(model=self.config.model,messages=messages,stream=False,keep_alive=0,
            options=dict(temperature=0,seed=self.config.seed,num_predict=self.config.max_tokens,num_ctx=8192))
        if schema is not None:
            payload['format'] = deepcopy(schema)
        url=urlsplit(self.config.endpoint);connection=HTTPConnection('127.0.0.1',url.port,timeout=self.config.timeout)
        try:
            connection.request('POST','/api/chat',json.dumps(payload).encode(),{'Content-Type':'application/json'})
            response=connection.getresponse()
            if response.status!=200:raise LocalModelError(f'Local model returned HTTP {response.status}; no draft saved')
            if response.getheader('Content-Type','').split(';')[0]!='application/json':
                raise LocalModelError('Local model returned a non-JSON response')
            raw=response.read(65_537)
            if len(raw)>65_536:raise LocalModelError('Local model response exceeds 65,536 bytes')
            try:result=json.loads(raw)
            except (ValueError,UnicodeError,RecursionError):raise LocalModelError('Local model returned invalid JSON') from None
            self.identity.check_response(result)
            if (not isinstance(result,dict) or result.get('done') is not True or result.get('done_reason')!='stop'
                    or not isinstance(result.get('message'),dict) or result['message'].get('role')!='assistant'
                    or result['message'].get('tool_calls')):
                raise LocalModelError('Local model response is incomplete or requests unsupported tools')
            return result['message'].get('content')
        except (OSError,HTTPException):raise LocalModelError('Local model unavailable or timed out; no fallback or draft saved') from None
        finally:connection.close()
