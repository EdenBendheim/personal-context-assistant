"""Generated wording with inspectable support, never automatic factual approval."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Protocol

from .drafts import CitedQuote, DraftRequest, ReviewPacket
from .memory import nonempty


@dataclass(frozen=True)
class GeneratedSegment:
    text: str
    kind: str
    support: tuple[CitedQuote, ...] = ()


@dataclass(frozen=True)
class GeneratedProposal:
    segments: tuple[GeneratedSegment, ...] = ()
    abstain_reason: str | None = None


class GenerationProvider(Protocol):
    def generate(self, packet: ReviewPacket) -> GeneratedProposal: ...


def validate_proposal(proposal: GeneratedProposal, packet: ReviewPacket) -> dict:
    if not isinstance(proposal, GeneratedProposal):
        raise ValueError('Provider must return a generated proposal')
    if not isinstance(proposal.segments, (list, tuple)) or len(proposal.segments) > 12:
        raise ValueError('Proposal must contain at most 12 segments')
    if proposal.abstain_reason is not None:
        reason = nonempty(proposal.abstain_reason, 'Abstention reason')
        if proposal.segments or len(reason) > 500:
            raise ValueError('Abstention requires no segments and a bounded reason')
        return dict(status='provider_abstained', draft_text='', citations=[], segments=[], review_notes=[reason])
    if not proposal.segments:
        raise ValueError('Provide wording or an explicit abstention')
    known = {item.key:item for item in packet.evidence}
    segments, citations, labels = [], [], {}
    for segment in proposal.segments:
        if not isinstance(segment, GeneratedSegment) or segment.kind not in ('fact', 'social', 'question'):
            raise ValueError('Invalid generated segment kind')
        text = nonempty(segment.text, 'Generated wording')
        if len(text) > 2000 or not isinstance(segment.support, (tuple, list)) or len(segment.support) > 4:
            raise ValueError('Generated wording/support exceeds bounds')
        if segment.kind == 'fact' and not segment.support:
            raise ValueError('Factual wording requires cited support for human inspection')
        ids, seen = [], set()
        for quote in segment.support:
            if not isinstance(quote, CitedQuote) or not isinstance(quote.evidence_key, str):
                raise ValueError('Invalid generated support')
            value = nonempty(quote.quote, 'Support quote')
            item = known.get(quote.evidence_key)
            if item is None or value not in item.text or len(value) > 500:
                raise ValueError('Generated support must quote available factual evidence literally')
            key = (item.key, value)
            if key in seen:
                raise ValueError('Duplicate support within a segment')
            seen.add(key)
            if key not in labels:
                labels[key] = len(citations)+1
                citations.append(dict(label=labels[key], evidence_key=item.key, kind=item.kind,
                    quote=value, provenance=deepcopy(item.provenance)))
            ids.append(labels[key])
        segments.append(dict(text=text, kind=segment.kind, citation_labels=ids))
    wording = '\n\n'.join(s['text'] for s in segments)
    if len(wording) > 6000:
        raise ValueError('Generated draft exceeds 6,000 characters')
    return dict(status='needs_review', draft_text=wording, citations=citations, segments=segments,
        generation_kind='generative', support_review_required=True,
        review_notes=['Every segment requires human factual and wording review before a usable rating.',
            'Literal support proves quote provenance, not that generated wording follows from it.',
            'Segment kinds are provider suggestions: social/question text can still contain unsupported claims.',
            'This draft is not approval or authorization to send a message.'])


def generate(engine, request: DraftRequest, provider: GenerationProvider) -> dict:
    packet = engine.prepare(request)
    if request.mode != 'generic' and not packet.evidence:
        return dict(status='needs_history', draft_text='', citations=[], packet=asdict(packet),
            packet_sha256=packet.fingerprint, review_notes=['Add relevant factual history before generation.'])
    proposal = provider.generate(deepcopy(packet))
    result = validate_proposal(proposal, packet)
    if engine.prepare(request).fingerprint != packet.fingerprint:
        raise ValueError('Context changed during generation; rebuild the draft')
    return result | dict(packet=asdict(packet), packet_sha256=packet.fingerprint, provider=type(provider).__name__)
