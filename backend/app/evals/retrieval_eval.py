"""Scores retrieval quality against the golden set, independent of Claude.

Runs rag.retrieve() directly (no generation call) and checks whether the
expected procedure(s) actually come back in the top-k results.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.evals.golden_set import GOLDEN_SET, GoldenItem
from app.services import rag


@dataclass
class RetrievalResult:
    item: GoldenItem
    retrieved_titles: list[str]
    hit: bool  # at least one expected source retrieved (n/a for out-of-scope items)
    precision_at_k: float
    reciprocal_rank: float


@dataclass
class RetrievalReport:
    results: list[RetrievalResult] = field(default_factory=list)

    @property
    def in_scope_results(self) -> list[RetrievalResult]:
        return [r for r in self.results if r.item.expected_sources]

    @property
    def out_of_scope_results(self) -> list[RetrievalResult]:
        return [r for r in self.results if not r.item.expected_sources]

    @property
    def recall_at_k(self) -> float:
        in_scope = self.in_scope_results
        if not in_scope:
            return 0.0
        return sum(r.hit for r in in_scope) / len(in_scope)

    @property
    def mean_reciprocal_rank(self) -> float:
        in_scope = self.in_scope_results
        if not in_scope:
            return 0.0
        return sum(r.reciprocal_rank for r in in_scope) / len(in_scope)

    @property
    def mean_precision_at_k(self) -> float:
        in_scope = self.in_scope_results
        if not in_scope:
            return 0.0
        return sum(r.precision_at_k for r in in_scope) / len(in_scope)

    @property
    def false_positive_rate(self) -> float:
        """Out-of-scope questions where retrieval still returned any chunk at all."""
        out_of_scope = self.out_of_scope_results
        if not out_of_scope:
            return 0.0
        return sum(1 for r in out_of_scope if r.retrieved_titles) / len(out_of_scope)


def evaluate_retrieval(db: Session, top_k: int = 4) -> RetrievalReport:
    report = RetrievalReport()

    for item in GOLDEN_SET:
        sources = rag.retrieve(db, item.question, top_k=top_k)
        retrieved_titles = [s.title for s in sources]
        expected = set(item.expected_sources)

        hit = any(title in expected for title in retrieved_titles)

        relevant_count = sum(1 for title in retrieved_titles if title in expected)
        precision = relevant_count / len(retrieved_titles) if retrieved_titles else 0.0

        reciprocal_rank = 0.0
        for rank, title in enumerate(retrieved_titles, start=1):
            if title in expected:
                reciprocal_rank = 1 / rank
                break

        report.results.append(
            RetrievalResult(
                item=item,
                retrieved_titles=retrieved_titles,
                hit=hit,
                precision_at_k=precision,
                reciprocal_rank=reciprocal_rank,
            )
        )

    return report
