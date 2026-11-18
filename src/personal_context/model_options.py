"""Shared explicit local-inference configuration for CLI entry points."""
from .local_model import LocalModelConfig,OllamaProvider
from .generation_format import PROMPTS,PROMPT_VERSION


def add_model_options(parser):
    parser.add_argument('--local-model',help='Already installed local Ollama model; omitted uses extractive baseline')
    parser.add_argument('--model-endpoint',default='http://127.0.0.1:11434')
    parser.add_argument('--model-timeout',type=float,default=30)
    parser.add_argument('--model-max-tokens',type=int,default=1024)
    parser.add_argument('--model-seed',type=int,default=29)
    parser.add_argument('--expected-model-digest',help='Pin the exact installed local model digest')
    parser.add_argument('--draft-prompt', choices=tuple(PROMPTS), default=PROMPT_VERSION,
                        help='Versioned drafting instructions; v5 is experimental')
    parser.add_argument('--response-format', choices=('union_schema', 'prompt_only'), default='union_schema',
                        help='Decoder constraint; strict response validation applies to both')
    parser.add_argument('--confirm-local-only',action='store_true',help='Confirm the Ollama daemon has cloud disabled')


def configured_provider(args):
    if args.local_model is None:
        if (args.confirm_local_only or args.model_endpoint!='http://127.0.0.1:11434'
                or args.model_timeout!=30 or args.model_max_tokens!=1024 or args.model_seed!=29 or args.expected_model_digest is not None
                or args.draft_prompt!=PROMPT_VERSION or args.response_format!='union_schema'):
            raise ValueError('Model options require --local-model; no inference is enabled by default')
        return None
    return OllamaProvider(LocalModelConfig(args.local_model,args.model_endpoint,args.model_timeout,
        args.model_max_tokens,args.model_seed,args.confirm_local_only,expected_digest=args.expected_model_digest,
        prompt_version=args.draft_prompt,response_format=args.response_format))
