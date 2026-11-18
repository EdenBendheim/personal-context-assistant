"""Render a self-contained local form for a masked synthetic review packet."""

import base64
import hashlib
import json
from pathlib import Path

from .frozen_retrieval import digest
from .reply_quality import validate_review_key


def rating_template(packet):
    return dict(version=1, packet_sha256=digest(packet), reviewer_kind=None, prior_exposure=None,
                ratings={candidate['id']: dict(support=None, completed=[], note='')
                         for case in packet['cases'] for candidate in case['candidates']})


def render_review_form(packet, key):
    validate_review_key(packet, key)
    assets = Path(__file__).with_name('web')
    script = (assets/'reply_review.js').read_text()
    style = (assets/'reply_review.css').read_text()
    encoded = json.dumps(dict(packet=packet, rating_template=rating_template(packet)),
                         ensure_ascii=True, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e')
    if len(encoded.encode()) > 1_000_000:
        raise ValueError('Review packet exceeds the local form size limit')
    def sha(content):
        return base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
    policy = (f"default-src 'none'; script-src 'sha256-{sha(script)}'; "
              f"style-src 'sha256-{sha(style)}'; connect-src 'none'; form-action 'none'; base-uri 'none'")
    return ((assets/'reply_review.html').read_text().replace('__POLICY__', policy)
            .replace('__STYLE__', style).replace('__SCRIPT__', script).replace('__DATA__', encoded))
