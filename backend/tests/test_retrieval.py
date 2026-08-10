"""Tests retrieval and citation-checking against the already-seeded corpus
(synthetic + real documents) — read-only, no fixtures created/destroyed.
"""

from app.services import rag


def test_chunk_text_bounds_oversized_single_paragraph_and_preserves_overlap():
    text = " ".join(f"word{i}" for i in range(500))
    chunks = rag.chunk_text(text, chunk_size=120, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert chunks[0][-20:] in chunks[1]


def test_chunk_text_rejects_invalid_overlap():
    import pytest

    with pytest.raises(ValueError, match="smaller than chunk_size"):
        rag.chunk_text("some text", chunk_size=100, overlap=100)


def test_retrieve_finds_the_right_synthetic_document(db):
    sources = rag.retrieve(db, "How should we handle tonight's peak?", top_k=4)
    assert any(s.title == "Peak Demand Response" for s in sources)


def test_retrieve_finds_the_right_real_document(db):
    sources = rag.retrieve(db, "What was CAISO's actual 2019 summer peak demand?", top_k=4)
    assert any(s.title == "2020 Summer Loads and Resources Assessment" for s in sources)
    # and it should carry a real page number, unlike the synthetic docs
    hit = next(s for s in sources if s.title == "2020 Summer Loads and Resources Assessment")
    assert hit.page_number is not None


def test_retrieve_rejects_clearly_unrelated_question(db):
    sources = rag.retrieve(db, "A wildfire is threatening a substation near this region. What's our procedure?", top_k=4)
    assert sources == []


def test_metadata_filter_by_organization_excludes_other_orgs(db):
    sources = rag.retrieve(db, "How should we handle tonight's peak?", top_k=4, organization="synthetic")
    assert len(sources) > 0
    assert all(s.organization == "synthetic" for s in sources)


def test_metadata_filter_can_return_empty_when_nothing_matches(db):
    sources = rag.retrieve(db, "How should we handle tonight's peak?", top_k=4, organization="nonexistent_org")
    assert sources == []


def test_extract_citations_matches_real_titles():
    matched, unmatched = rag.extract_citations(
        "Dispatch batteries now. [Source: Peak Demand Response]", ["Peak Demand Response", "Solar Duck Curve Ramp"]
    )
    assert matched == ["Peak Demand Response"]
    assert unmatched == []


def test_extract_citations_flags_fabricated_source():
    matched, unmatched = rag.extract_citations(
        "Do this. [Source: Some Document That Was Never Retrieved]", ["Peak Demand Response"]
    )
    assert matched == []
    assert unmatched == ["Some Document That Was Never Retrieved"]


def test_extract_citations_handles_page_aware_format():
    # [Source: <title>, p.<page>] must still match by substring containment
    matched, unmatched = rag.extract_citations(
        "As specified. [Source: EOP-011-4 — Emergency Operations, p.3]", ["EOP-011-4 — Emergency Operations"]
    )
    assert matched == ["EOP-011-4 — Emergency Operations"]
    assert unmatched == []
