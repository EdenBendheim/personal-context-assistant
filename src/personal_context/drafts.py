"""Reviewable extractive drafting: history boundaries, citations, and provider isolation."""

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Protocol

from .memory import Memory, nonempty, scope
from .messages import Message, utc_timestamp
from .store import Store


@dataclass(frozen=True)
class DraftRequest:
    owner: str
    contact: str
    before: str
    query: str
    mode: str = "personalized"
    limit: int = 5

    def __post_init__(self):
        owner, contact = scope(self.owner, self.contact)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "contact", contact)
        object.__setattr__(self, "before", utc_timestamp(self.before))
        object.__setattr__(self, "query", nonempty(self.query, "Query"))
        if self.mode not in ("generic", "context", "personalized"):
            raise ValueError("Mode must be generic, context, or personalized")
        if type(self.limit) is not int or not 1 <= self.limit <= 20:
            raise ValueError("Context limit must be an integer from 1 to 20")


@dataclass(frozen=True)
class Evidence:
    key: str
    kind: str
    text: str
    provenance: dict


@dataclass(frozen=True)
class ReviewPacket:
    request: DraftRequest
    evidence: tuple[Evidence, ...]
    style_examples: tuple[dict, ...]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class CitedQuote:
    evidence_key: str
    quote: str


class QuoteProvider(Protocol):
    """Providers select literal historical quotes, not arbitrary factual prose.

    A future generative provider needs a separate entailment/review contract.
    Source text and style examples are data; they cannot change these rules.
    """
    def select_quotes(self, packet: ReviewPacket) -> list[CitedQuote]: ...


class ExtractiveProvider:
    """Deterministic local baseline; no language model, API, or style imitation."""
    def select_quotes(self, packet: ReviewPacket) -> list[CitedQuote]:
        return [CitedQuote(item.key, item.text[:220]) for item in packet.evidence[:3]]


class DraftEngine:
    def __init__(self, store: Store, memory: Memory | None = None):
        self.store = store
        self.memory = memory if memory is not None else Memory(store)

    def _check_message(self, row: dict, request: DraftRequest):
        original = self.store.connection.execute("""SELECT id, source, thread, author, recipient, timestamp, body
            FROM messages WHERE source = ? AND id = ?""", (row["source"], row["id"])).fetchone()
        if original is None:
            raise ValueError("Retrieved source no longer exists")
        message = Message(**dict(original))
        fields = {key:row[key] for key in Message.__dataclass_fields__}
        if fields != dict(original):
            raise ValueError("Retrieved message differs from its stored source")
        pair = (request.owner, request.contact)
        if (message.author, message.recipient) not in (pair, pair[::-1]) or message.timestamp >= request.before:
            raise ValueError("Retrieved source crosses the contact/time boundary")

    def prepare(self, request: DraftRequest) -> ReviewPacket:
        if request.mode == "generic":
            return ReviewPacket(request, (), ())
        parameters = dict(owner=request.owner, contact=request.contact, before=request.before, limit=request.limit)
        evidence = []
        messages = self.store.search(request.query, **parameters)
        for index, row in enumerate(messages, 1):
            self._check_message(row, request)
            provenance = {key:row[key] for key in Message.__dataclass_fields__ if key != "body"}
            provenance["fingerprint"] = Message(**{key:row[key] for key in Message.__dataclass_fields__}).fingerprint
            evidence.append(Evidence(f"message-{index}", "message", row["body"], provenance))
        examples = ()
        if request.mode == "personalized":
            for index, item in enumerate(self.memory.context(**parameters), 1):
                evidence.append(Evidence(f"memory-{index}", "memory", item["text"],
                                         {key:value for key,value in item.items() if key != "text"}))
            examples = tuple(self.store.style_examples(**parameters))
            for row in examples:
                self._check_message(row, request)
                if row["author"] != request.owner:
                    raise ValueError("Another person's writing cannot be an owner style example")
        return ReviewPacket(request, tuple(evidence), examples)

    def draft(self, request: DraftRequest, provider: QuoteProvider | None = None) -> dict:
        packet = self.prepare(request)
        if request.mode != "generic" and not packet.evidence:
            return dict(status="needs_history", draft_text="", citations=[], packet=asdict(packet),
                        packet_sha256=packet.fingerprint,
                        review_notes=["Add relevant messages or reviewed memory before drafting factual context."])
        provider = provider if provider is not None else ExtractiveProvider()
        # The provider never receives mutable references to the engine's validation snapshot.
        quotes = provider.select_quotes(deepcopy(packet))
        if not isinstance(quotes, (list, tuple)) or len(quotes) > 3:
            raise ValueError("Provider must return at most three cited quotes")
        known = {item.key:item for item in packet.evidence}
        citations, seen = [], set()
        for quote in quotes:
            if not isinstance(quote, CitedQuote) or not isinstance(quote.evidence_key, str):
                raise ValueError("Provider returned an invalid cited quote")
            text = nonempty(quote.quote, "Quote")
            item = known.get(quote.evidence_key)
            if item is None or text not in item.text or len(text) > 220:
                raise ValueError("Quote is unsupported by an available evidence item")
            if (quote.evidence_key, text) in seen:
                raise ValueError("Provider returned a duplicate citation")
            seen.add((quote.evidence_key, text))
            citations.append(dict(label=len(citations)+1, evidence_key=item.key, kind=item.kind,
                                  quote=text, provenance=item.provenance))
        # Revocations, source edits, and newer history during a provider call invalidate the packet.
        if self.prepare(request).fingerprint != packet.fingerprint:
            raise ValueError("Context changed during drafting; rebuild and review the packet")
        lines = ["Hi,", "", f"Following up on: {request.query}", ""]
        if citations:
            lines += ["For reference, earlier context includes:"]
            for citation in citations:
                lines += [f'[{citation["label"]}] Historical {citation["kind"]}:']
                lines += [f"> {line}" for line in citation["quote"].splitlines()]
            lines.append("")
        lines += ["[Add your response or proposed next step here.]", "", "Thanks!"]
        return dict(status="needs_review", draft_text="\n".join(lines), citations=citations,
                    packet=asdict(packet), packet_sha256=packet.fingerprint, provider=type(provider).__name__,
                    review_notes=["Quoted history may be outdated; review the wording and citations.",
                                  "This extractive template does not generate or imitate your writing style.",
                                  "Source citations establish quote provenance, not automatic factual entailment."])
