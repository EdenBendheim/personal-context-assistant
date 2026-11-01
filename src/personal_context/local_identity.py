"""Read-only loopback runtime/model receipts and optional local blob verification."""
import argparse
from copy import deepcopy
import hashlib
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .local_model import LocalModelConfig, LocalModelError


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _json(config, path, payload=None):
    connection = HTTPConnection('127.0.0.1', urlsplit(config.endpoint).port, timeout=config.timeout)
    try:
        connection.request('GET' if payload is None else 'POST', path,
            None if payload is None else json.dumps(payload).encode(), {'Content-Type':'application/json'})
        response = connection.getresponse()
        if response.status != 200 or response.getheader('Content-Type', '').split(';')[0] != 'application/json':
            raise LocalModelError('Local model inspection returned an unsupported status/content type')
        raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise LocalModelError('Local model inspection exceeds 1 MiB')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise LocalModelError('Local model inspection must return a JSON object')
        return result
    except (OSError, HTTPException):
        raise LocalModelError('Local model inspection unavailable or timed out') from None
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise LocalModelError('Local model inspection returned invalid JSON') from None
    finally:
        connection.close()


def inspect_model(config, *, expected_digest=None, capability=None):
    # Revalidate even when called with an embedding config rather than chat config.
    checked = LocalModelConfig(model=config.model, endpoint=config.endpoint, timeout=config.timeout,
                               local_only_confirmed=config.local_only_confirmed)
    version = _json(checked, '/api/version').get('version')
    models = _json(checked, '/api/tags').get('models')
    if (not isinstance(version, str) or not re.fullmatch('[A-Za-z0-9_.+-]{1,100}', version)
            or not isinstance(models, list) or len(models) > 1000):
        raise LocalModelError('Invalid local runtime or model inventory')
    found = [m for m in models if isinstance(m, dict) and m.get('name') == checked.model]
    if len(found) != 1:
        raise LocalModelError('Choose one exact installed model tag from the local inventory')
    model = found[0]
    digest, size = model.get('digest'), model.get('size')
    if (not _sha(digest) or type(size) is not int or not 0 < size <= 20*1024**3
            or (expected_digest is not None and (not _sha(expected_digest) or digest != expected_digest))):
        raise LocalModelError('Installed model digest or size differs from the expected identity')
    shown = _json(checked, '/api/show', dict(model=checked.model))
    capabilities = shown.get('capabilities')
    details = shown.get('details')
    if (shown.get('remote_host') or shown.get('remote_model') or not isinstance(details, dict)
            or not isinstance(capabilities, list) or any(not isinstance(c, str) for c in capabilities)
            or capability is not None and capability not in capabilities):
        raise LocalModelError('Model capability or local-only metadata differs')
    return dict(version=1, model=checked.model, digest=digest, size_bytes=size, runtime_version=version,
        capabilities=capabilities, details={k: details.get(k) for k in ('format', 'family', 'parameter_size', 'quantization_level')},
        show_sha256=hashlib.sha256(json.dumps(shown, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
        local_only_confirmed=True,
        limitation='Daemon-reported model identity; this does not inspect its environment, authenticate its producer or measure quality')


class ModelIdentityGuard:
    """Optional stable identity checked around each inference request."""
    def __init__(self, config, capability):
        self.config, self.capability, self.snapshot = config, capability, None

    def capture(self):
        digest = self.config.expected_digest
        if digest is None:
            return None
        current = inspect_model(self.config, expected_digest=digest, capability=self.capability)
        if self.snapshot is not None and current != self.snapshot:
            raise LocalModelError('Local model/runtime identity changed during inference')
        self.snapshot = deepcopy(current)
        return deepcopy(current)

    def check_response(self, response):
        if self.config.expected_digest is not None:
            if not isinstance(response, dict) or response.get('model') != self.config.model:
                raise LocalModelError('Inference response does not name the pinned model')
            self.capture()


def _file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_files(identity, model_directory, manifest_path):
    """Check explicitly supplied local manifest/blob bytes without publishing paths."""
    root, path = Path(model_directory).resolve(), Path(manifest_path).resolve()
    if not _sha(identity.get('digest')) or not path.is_relative_to(root/'manifests'):
        raise ValueError('Choose a model manifest inside the explicit local model directory')
    if path.stat().st_size > 1_048_576:
        raise ValueError('Local manifest exceeds 1 MiB')
    manifest_file_sha = _file_sha(path)
    manifest = json.loads(path.read_text())
    layers = manifest.get('layers')
    if not isinstance(layers, list) or not 1 <= len(layers) <= 32 or not isinstance(manifest.get('config'), dict):
        raise ValueError('Invalid bounded local model manifest')
    records = []
    for layer in [manifest['config'], *layers]:
        digest, size = layer.get('digest'), layer.get('size')
        if (not isinstance(digest, str) or not digest.startswith('sha256:') or not _sha(digest[7:])
                or type(size) is not int or not 0 < size <= 20*1024**3):
            raise ValueError('Invalid local model blob identity')
        blob = (root/'blobs'/('sha256-'+digest[7:])).resolve()
        if (not blob.is_relative_to(root/'blobs') or blob.stat().st_size != size or _file_sha(blob) != digest[7:]):
            raise ValueError('Local model blob bytes differ from their manifest')
        records.append(dict(digest=digest, size_bytes=size))
    binding = 'direct_manifest'
    if manifest_file_sha != identity['digest']:
        # Some runtimes retain the registry manifest as an extra manifest layer.
        origins = [layer for layer in layers if layer.get('mediaType') == 'application/vnd.docker.distribution.manifest.v2+json'
                   and layer.get('digest') == 'sha256:'+identity['digest']]
        if len(origins) != 1 or origins[0]['size'] > 1_048_576:
            raise ValueError('Local manifest cannot be bound to the daemon model digest')
        source = root/'blobs'/('sha256-'+identity['digest'])
        original = json.loads(source.read_text())
        if manifest | dict(layers=[layer for layer in layers if layer is not origins[0]]) != original:
            raise ValueError('Local wrapper differs from its verified registry manifest')
        binding = 'retained_registry_manifest'
    return dict(manifest_sha256=identity['digest'], manifest_file_sha256=manifest_file_sha,
                digest_binding=binding, verified_blobs=records,
                total_blob_bytes=sum(r['size_bytes'] for r in records),
                paths_omitted=True, limitation='Verified local file bytes, not a signed producer or served-weight attestation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--confirm-local-only', action='store_true')
    parser.add_argument('--expected-digest')
    parser.add_argument('--capability', choices=('completion', 'embedding'))
    parser.add_argument('--model-directory', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    try:
        config = LocalModelConfig(model=args.model, endpoint=args.endpoint, local_only_confirmed=args.confirm_local_only)
        result = inspect_model(config, expected_digest=args.expected_digest, capability=args.capability)
        if bool(args.model_directory) != bool(args.manifest):
            raise ValueError('File verification requires both --model-directory and --manifest')
        if args.manifest:
            result['file_verification'] = verify_model_files(result, args.model_directory, args.manifest)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.exit(2, f'Local identity check failed: {exc}\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
