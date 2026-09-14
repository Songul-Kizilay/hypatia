"""Transient exact-evidence input, not permission to disclose or call a model.

The caller must verify current run membership and chunk integrity, and authorize
the destination and charge the original allowance before using an adapter.
This fingerprint detects changed inputs; it is not a second plan digest.
"""

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord


@dataclass(frozen=True, slots=True)
class SemanticComparisonRequest:
    run_id: str
    question: str = field(repr=False)
    evidence: tuple[ResearchEvidenceRecord, ...] = field(repr=False)
    limit: int = 3
    content_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.run_id, str)
            or not self.run_id.strip()
            or len(self.run_id) > 200
            or not isinstance(self.question, str)
            or not self.question.strip()
            or len(self.question) > 2000
            or type(self.limit) is not int
            or not 1 <= self.limit <= 3
            or not isinstance(self.evidence, tuple)
            or len(self.evidence) != 2
            or any(not isinstance(e, ResearchEvidenceRecord) for e in self.evidence)
        ):
            raise ResearchError("Invalid bounded semantic comparison input.")
        if (
            len({e.evidence_id for e in self.evidence}) != 2
            or len({e.source_document_id for e in self.evidence}) != 2
            or any(
                len(value) > 200
                for e in self.evidence
                for value in (e.evidence_id, e.source_document_id, e.chunk_id)
            )
        ):
            raise ResearchError("Comparison requires distinct bounded evidence IDs.")
        try:
            # Bind the full canonical records, including truncation and hashes;
            # model aliases cannot supply or rewrite provenance.
            payload = {
                "schema": "hypatia:semantic-comparison-input:v1",
                "run_id": self.run_id,
                "question": self.question,
                "limit": self.limit,
                "evidence": [
                    {**asdict(e), "recorded_at": e.recorded_at.isoformat()}
                    for e in self.evidence
                ],
            }
            encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode(
                "utf-8"
            )
            if len(self.model_input_json().encode("utf-8")) > 16_384:
                raise ValueError("Model input too large.")
        except ValueError, TypeError:
            raise ResearchError("Invalid semantic comparison encoding.") from None
        object.__setattr__(self, "content_fingerprint", sha256(encoded).hexdigest())

    def model_input_json(self) -> str:
        """Only question and excerpts go to the model, never notes or IDs."""
        return json.dumps(
            {
                "question": self.question,
                "evidence": [
                    {
                        "source": str(index),
                        "excerpt": e.excerpt,
                        "excerpt_truncated": e.excerpt_truncated,
                    }
                    for index, e in enumerate(self.evidence)
                ],
            },
            ensure_ascii=False,
        )
