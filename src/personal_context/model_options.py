"""Shared explicit local-inference configuration for CLI entry points."""
from .local_model import LocalModelConfig,OllamaProvider


def add_model_options(parser):
    parser.add_argument('--local-model',help='Already installed local Ollama model; omitted uses extractive baseline')
    parser.add_argument('--model-endpoint',default='http://127.0.0.1:11434')
    parser.add_argument('--model-timeout',type=float,default=30)
    parser.add_argument('--model-max-tokens',type=int,default=1024)
    parser.add_argument('--model-seed',type=int,default=29)
    parser.add_argument('--confirm-local-only',action='store_true',help='Confirm the Ollama daemon has cloud disabled')


def configured_provider(args):
    if args.local_model is None:
        if (args.confirm_local_only or args.model_endpoint!='http://127.0.0.1:11434'
                or args.model_timeout!=30 or args.model_max_tokens!=1024 or args.model_seed!=29):
            raise ValueError('Model options require --local-model; no inference is enabled by default')
        return None
    return OllamaProvider(LocalModelConfig(args.local_model,args.model_endpoint,args.model_timeout,
        args.model_max_tokens,args.model_seed,args.confirm_local_only))
