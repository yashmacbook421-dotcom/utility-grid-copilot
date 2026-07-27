"""RAG pipeline: chunk + embed grid operating procedures, retrieve by similarity,
then ground a Claude answer in the retrieved passages (+ live forecast context).
"""

import re
from dataclasses import dataclass

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ProcedureDocument
from app.schemas import SourceCitation
from app.services.embeddings import embed_text, embed_texts

_CHUNK_SIZE_CHARS = 900
_CHUNK_OVERLAP_CHARS = 150


def chunk_text(text: str, chunk_size: int = _CHUNK_SIZE_CHARS, overlap: int = _CHUNK_OVERLAP_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        if len(buffer) + len(para) + 1 <= chunk_size:
            buffer = f"{buffer}\n\n{para}".strip()
            continue
        if buffer:
            chunks.append(buffer)
        buffer = para[-overlap:] + "\n\n" + para if len(para) > chunk_size else para

    if buffer:
        chunks.append(buffer)

    return chunks


def ingest_document(db: Session, source: str, title: str, content: str, metadata: dict | None = None) -> list[str]:
    chunks = chunk_text(content)
    if not chunks:
        return []

    vectors = embed_texts(chunks)
    for chunk, vector in zip(chunks, vectors):
        db.add(
            ProcedureDocument(
                source=source,
                title=title,
                content=chunk,
                embedding=vector,
                doc_metadata=metadata or {},
            )
        )
    db.commit()
    return chunks


# Below this similarity, a chunk is noise rather than a genuine match. Picked
# empirically from the eval golden set: every in-scope question's top match is
# >=0.43, while out-of-scope questions (wildfire/SCADA) top out at 0.371 — 0.40
# sits in the gap. Without this, top-k retrieval always returns *something*,
# even for questions with no matching procedure (see eval false-positive rate).
_MIN_SIMILARITY = 0.40


def retrieve(db: Session, query: str, top_k: int = 4) -> list[SourceCitation]:
    query_vector = embed_text(query)
    distance = ProcedureDocument.embedding.cosine_distance(query_vector)

    stmt = select(ProcedureDocument, distance.label("distance")).order_by(distance).limit(top_k)
    results = db.execute(stmt).all()

    return [
        SourceCitation(
            title=doc.title,
            source=doc.source,
            excerpt=doc.content,
            similarity=round(1 - float(dist), 4),
        )
        for doc, dist in results
        if 1 - float(dist) >= _MIN_SIMILARITY
    ]


_CITATION_BLOCK_PATTERN = re.compile(r"\[Source:\s*([^\]]+)\]")


def extract_citations(answer: str, retrieved_titles: list[str]) -> tuple[list[str], list[str]]:
    """Pulls titles out of `[Source: X]` blocks and matches them against the
    retrieved titles by substring containment, not exact equality — the system
    prompt only says to cite like `[Source: <title>]`, so in practice Claude
    formats multi-citations inconsistently (`A; Source: B`, `A / B`,
    `A, Step 3`). A block counts as matched as soon as ANY retrieved title
    appears in it — trailing text like ", Step 3" or ", Interaction with solar
    ramp" is a section reference, not a second citation, so it's not held
    against the block. Only a block containing no retrieved title at all is
    unmatched. Returns (matched_titles, unmatched_blocks) — a non-empty second
    element means the answer cited something it wasn't given as context.
    """
    matched: list[str] = []
    unmatched: list[str] = []

    for block in _CITATION_BLOCK_PATTERN.findall(answer):
        block_titles = [title for title in retrieved_titles if title in block]
        if block_titles:
            matched.extend(block_titles)
        else:
            unmatched.append(block.strip())

    return matched, unmatched


def summarize_forecast(forecast_data: dict) -> str:
    peak = forecast_data["peak_forecast_mw"]
    peak_time = forecast_data["peak_forecast_time"]
    first = forecast_data["forecast"][0]
    return (
        f"Next forecast point: {first['predicted_demand_mw']} MW "
        f"(range {first['lower_bound_mw']}-{first['upper_bound_mw']} MW) at {first['time']}. "
        f"Forecast peak: {peak} MW at {peak_time}."
    )


SYSTEM_PROMPT = """You are a grid operations copilot for a utility company. You help operators \
decide how to respond to demand forecasts using the utility's own operating procedures.

Rules:
- Ground every recommendation in the provided procedure excerpts. Cite them inline like [Source: <title>].
- If the forecast context shows a demand spike or peak, address it directly and explain why (e.g. temperature, \
EV charging load, solar drop-off in the evening ramp).
- If the retrieved procedures don't cover the situation, say so explicitly rather than inventing a procedure.
- Be concise and operational: an on-shift engineer should be able to act on your answer immediately.
"""


@dataclass
class GenerationResult:
    answer: str
    input_tokens: int
    output_tokens: int


def generate_answer(
    client: Anthropic,
    model: str,
    question: str,
    region: str,
    sources: list[SourceCitation],
    forecast_summary: str | None,
) -> GenerationResult:
    context_blocks = "\n\n".join(f"[Source: {s.title}]\n{s.excerpt}" for s in sources) or "No matching procedures found."

    forecast_block = f"\n\nCurrent forecast context for {region}:\n{forecast_summary}" if forecast_summary else ""

    user_message = (
        f"Region: {region}\n"
        f"Operator question: {question}{forecast_block}\n\n"
        f"Relevant operating procedures:\n{context_blocks}"
    )

    # 2048 rather than 1024: adaptive thinking's depth varies per question, and on
    # a 1024 budget a heavier thinking chain can occasionally consume the whole
    # thing before any visible text is written, returning an empty answer with
    # stop_reason="end_turn" (no error to catch). Seen in practice on solar-01
    # in the eval golden set — same failure mode fixed for the eval judge earlier.
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    answer = "".join(block.text for block in response.content if block.type == "text")
    if not answer.strip():
        answer = (
            "The copilot didn't produce a response for this question — please try rephrasing it "
            "or asking again."
        )
    return GenerationResult(
        answer=answer,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
