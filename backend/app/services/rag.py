"""RAG pipeline: chunk + embed grid operating procedures, retrieve by similarity,
then ground a Claude answer in the retrieved passages (+ live forecast context).
"""

import re

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
    ]


_SYSTEM_PROMPT = """You are a grid operations copilot for a utility company. You help operators \
decide how to respond to demand forecasts using the utility's own operating procedures.

Rules:
- Ground every recommendation in the provided procedure excerpts. Cite them inline like [Source: <title>].
- If the forecast context shows a demand spike or peak, address it directly and explain why (e.g. temperature, \
EV charging load, solar drop-off in the evening ramp).
- If the retrieved procedures don't cover the situation, say so explicitly rather than inventing a procedure.
- Be concise and operational: an on-shift engineer should be able to act on your answer immediately.
"""


def generate_answer(
    client: Anthropic,
    model: str,
    question: str,
    region: str,
    sources: list[SourceCitation],
    forecast_summary: str | None,
) -> str:
    context_blocks = "\n\n".join(f"[Source: {s.title}]\n{s.excerpt}" for s in sources) or "No matching procedures found."

    forecast_block = f"\n\nCurrent forecast context for {region}:\n{forecast_summary}" if forecast_summary else ""

    user_message = (
        f"Region: {region}\n"
        f"Operator question: {question}{forecast_block}\n\n"
        f"Relevant operating procedures:\n{context_blocks}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return "".join(block.text for block in response.content if block.type == "text")
