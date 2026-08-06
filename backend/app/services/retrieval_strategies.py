"""Three retrieval strategies over the same document_chunks corpus, sharing
one call signature (`db, query, top_k -> list[SourceCitation]`) so the eval
harness can swap between them and compare results.

- dense: the existing pgvector cosine-similarity search (rag.retrieve).
- sparse: Postgres full-text search (keyword/lexical), zero new dependencies.
- hybrid: reciprocal rank fusion of the two.

A cross-encoder reranker was deliberately left out — it would mean another
torch-based model, right after fixing a real memory blowout from exactly
that kind of dependency (see backend/Dockerfile). `rerank_with_llm` below
tests the alternative (asking Claude to re-score candidates, no new
dependency) — built and measured, not wired into production. Real result
on the 26-item golden set: precision@k improved 64.2% -> 70.4%, but MRR
regressed slightly (1.00 -> 0.97) and the false-positive-rate problem below
was unchanged (reranking reorders a candidate pool, it doesn't reject one —
a genuinely irrelevant candidate that clears retrieval's floor still gets
reordered, not dropped). Decided against production use: the deterministic
pipeline's whole value proposition (see ARCHITECTURE.md) is a single,
predictable Claude call per request — reranking adds a second sequential
call to every request for a real but modest precision gain that doesn't
even fix the bigger problem. Kept as a tested, available option, not a
default.

Known, measured limitation (2026-07-29): unlike dense retrieval, sparse (and
therefore hybrid) has no calibrated relevance floor equivalent to rag.py's
_MIN_SIMILARITY. Tried one — it doesn't work here: the out-of-scope
"wildfire near a substation" golden question scores the same top raw
ts_rank_cd (0.4) as a genuine in-scope match, because every procedure doc
shares boilerplate vocabulary ("procedure", "region", "demand") that
ts_rank_cd doesn't down-weight enough to reject. Dense embeddings correctly
recognize the wildfire question as semantically unrelated; lexical overlap
alone doesn't. This is a real, reportable weakness of naive full-text
search on a small, vocabulary-repetitive corpus — not something to
threshold away artificially.
"""

import json
import re

from anthropic import Anthropic
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.schemas import SourceCitation
from app.services import rag

_CANDIDATE_POOL = 10
_RRF_K = 60


def retrieve_dense(db: Session, query: str, top_k: int = 4) -> list[SourceCitation]:
    return rag.retrieve(db, query, top_k=top_k)


def _sparse_candidates(db: Session, query: str, limit: int) -> list[tuple[DocumentChunk, Document, float]]:
    # plainto_tsquery ANDs every term together — a single filler word in a
    # natural-language question (e.g. "tonight", which never appears in the
    # procedure docs) would zero out the match for every document. OR-ing
    # the query's lexemes instead is the standard fix for lexical search
    # over full questions rather than short keyword queries.
    query_lexemes = func.tsvector_to_array(func.to_tsvector("english", query))
    tsquery = func.to_tsquery("english", func.array_to_string(query_lexemes, " | "))
    tsvector = func.to_tsvector("english", DocumentChunk.content)
    rank = func.ts_rank_cd(tsvector, tsquery).label("rank")

    stmt = (
        select(DocumentChunk, Document, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(tsvector.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).all())


def _to_citation(chunk: DocumentChunk, document: Document, similarity: float) -> SourceCitation:
    return SourceCitation(
        title=document.title,
        source=document.source_url,
        excerpt=chunk.content,
        similarity=similarity,
        document_id=document.id,
        page_number=chunk.page_number,
        section=chunk.section,
        source_url=document.source_url,
        organization=document.organization,
    )


def retrieve_sparse(db: Session, query: str, top_k: int = 4) -> list[SourceCitation]:
    results = _sparse_candidates(db, query, top_k)
    if not results:
        return []

    ranks = [r for _, _, r in results]
    lo, hi = min(ranks), max(ranks)
    span = hi - lo

    def normalize(r: float) -> float:
        # ts_rank_cd isn't on a 0-1 scale like cosine similarity — min-max
        # normalized within this result set only, for display purposes.
        # Not comparable across queries or against dense/hybrid scores.
        return round((r - lo) / span, 4) if span > 0 else 1.0

    return [_to_citation(chunk, document, normalize(r)) for chunk, document, r in results]


def retrieve_hybrid(db: Session, query: str, top_k: int = 4) -> list[SourceCitation]:
    dense_stmt = (
        select(DocumentChunk, Document, DocumentChunk.embedding.cosine_distance(rag.embed_text(query)).label("distance"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .order_by("distance")
        .limit(_CANDIDATE_POOL)
    )
    dense_rows = list(db.execute(dense_stmt).all())
    sparse_rows = _sparse_candidates(db, query, _CANDIDATE_POOL)

    fused: dict = {}
    rows_by_chunk_id: dict = {}
    for rank, (chunk, document, _distance) in enumerate(dense_rows, start=1):
        rows_by_chunk_id[chunk.id] = (chunk, document)
        fused[chunk.id] = fused.get(chunk.id, 0.0) + 1 / (_RRF_K + rank)
    for rank, (chunk, document, _score) in enumerate(sparse_rows, start=1):
        rows_by_chunk_id[chunk.id] = (chunk, document)
        fused[chunk.id] = fused.get(chunk.id, 0.0) + 1 / (_RRF_K + rank)

    ranked_ids = sorted(fused, key=lambda chunk_id: fused[chunk_id], reverse=True)[:top_k]
    max_score = fused[ranked_ids[0]] if ranked_ids else 1.0

    return [
        _to_citation(*rows_by_chunk_id[chunk_id], round(fused[chunk_id] / max_score, 4) if max_score > 0 else 0.0)
        for chunk_id in ranked_ids
    ]


def rerank_with_llm(
    client: Anthropic, model: str, query: str, candidates: list[SourceCitation], top_k: int = 4
) -> list[SourceCitation]:
    """Asks Claude to re-score a candidate pool by relevance to the query,
    instead of trusting embedding-similarity order. Deliberately not a
    cross-encoder reranker — that would mean another torch-based model
    right after the CPU-only-torch memory fix. This trades latency/cost
    (one extra Claude call per query) for potentially better ordering, with
    no new dependency. Falls back to the original order if the model's
    response doesn't parse, rather than failing the request.
    """
    if not candidates:
        return []

    numbered = "\n\n".join(f"[{i}] {c.title}\n{c.excerpt[:400]}" for i, c in enumerate(candidates))
    prompt = (
        f"Question: {query}\n\n"
        f"Candidate passages:\n{numbered}\n\n"
        "Rate each candidate's relevance to answering the question, 0-10 (0=irrelevant, "
        "10=directly answers it). Respond with JSON only: a list of [index, score] pairs, "
        "e.g. [[0, 8], [1, 2]]."
    )
    response = client.messages.create(model=model, max_tokens=512, messages=[{"role": "user", "content": prompt}])
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        scores = dict(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return candidates[:top_k]

    ranked = sorted(range(len(candidates)), key=lambda i: scores.get(i, 0), reverse=True)
    return [candidates[i] for i in ranked[:top_k]]


STRATEGIES = {
    "dense": retrieve_dense,
    "sparse": retrieve_sparse,
    "hybrid": retrieve_hybrid,
}
