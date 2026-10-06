import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.document import Chunk, DocumentMetadata
from app.services.knowledge_service import (
    generate_document_knowledge,
    get_stored_knowledge,
    export_knowledge_as_markdown,
)
from app.services.storage import save_document
from app.models.search import SearchRequest

client = TestClient(app)


def test_knowledge_generation_and_persistence(tmp_path):
    doc_id = "test_doc_knowledge_01"
    doc_meta = DocumentMetadata(
        document_id=doc_id,
        filename="Test_Academic_Handbook.pdf",
        stored_filename=f"{doc_id}_Test.pdf",
        file_size_bytes=10240,
        pages=5,
        chunks_count=3,
        created_at="2026-10-06T12:00:00Z",
        status="processed",
        indexing_status="indexed",
        chunks=[
            Chunk(
                chunk_id=f"{doc_id}_c1",
                document_id=doc_id,
                source="Test_Academic_Handbook.pdf",
                page=1,
                text="Academic regulations require students to maintain minimum 75% attendance to qualify for examinations.",
            ),
            Chunk(
                chunk_id=f"{doc_id}_c2",
                document_id=doc_id,
                source="Test_Academic_Handbook.pdf",
                page=2,
                text="The minimum passing grade for undergraduate degree courses is C minus. Cumulative grade point average CGPA is calculated on a 10 point scale.",
            ),
            Chunk(
                chunk_id=f"{doc_id}_c3",
                document_id=doc_id,
                source="Test_Academic_Handbook.pdf",
                page=3,
                text="Enrolled students may borrow up to 5 books from the library for 14 days.",
            ),
        ],
    )
    save_document(doc_meta)

    # Generate knowledge
    knowledge = generate_document_knowledge(doc_id)
    assert knowledge is not None
    assert knowledge.document_id == doc_id
    assert knowledge.filename == "Test_Academic_Handbook.pdf"
    assert len(knowledge.categories) > 0

    cat_names = [c.name for c in knowledge.categories]
    assert "Academic" in cat_names or "Attendance" in cat_names

    # Check key facts
    assert len(knowledge.key_information) >= 2
    fact_titles = [f.title for f in knowledge.key_information]
    assert "Attendance Requirement" in fact_titles
    assert "Minimum Passing Grade" in fact_titles

    # Verify fact sources
    for fact in knowledge.key_information:
        assert fact.source_page in [1, 2, 3]
        assert fact.source_document == "Test_Academic_Handbook.pdf"

    # Verify suggested questions
    assert len(knowledge.suggested_questions) > 0
    for q in knowledge.suggested_questions:
        assert len(q.question) > 5
        assert q.category in cat_names

    # Verify persistence on disk
    stored = get_stored_knowledge(doc_id)
    assert stored is not None
    assert stored.document_id == doc_id
    assert len(stored.categories) == len(knowledge.categories)


def test_small_unstructured_document_truthfulness():
    """Verify that a small single-fact PDF does not fabricate unrelated categories like Hostel or Fees."""
    doc_id = "test_doc_minimal_truth"
    doc_meta = DocumentMetadata(
        document_id=doc_id,
        filename="Academic_Rules.pdf",
        stored_filename=f"{doc_id}_Rules.pdf",
        file_size_bytes=1024,
        pages=1,
        chunks_count=1,
        created_at="2026-10-06T12:00:00Z",
        status="processed",
        indexing_status="indexed",
        chunks=[
            Chunk(
                chunk_id=f"{doc_id}_c1",
                document_id=doc_id,
                source="Academic_Rules.pdf",
                page=1,
                text="Minimum passing grade for undergraduate courses is C minus.",
            )
        ],
    )
    save_document(doc_meta)

    knowledge = generate_document_knowledge(doc_id)
    assert knowledge is not None
    cat_names = [c.name for c in knowledge.categories]

    # Must contain Academic
    assert "Academic" in cat_names
    # Must NOT fabricate Hostel, Fees, or Transport
    assert "Hostel" not in cat_names
    assert "Fees & Finance" not in cat_names
    assert "Facilities" not in cat_names


def test_markdown_export():
    doc_id = "test_doc_export_md"
    doc_meta = DocumentMetadata(
        document_id=doc_id,
        filename="Test_Handbook.pdf",
        stored_filename=f"{doc_id}_Test.pdf",
        file_size_bytes=2048,
        pages=2,
        chunks_count=1,
        created_at="2026-10-06T12:00:00Z",
        status="processed",
        indexing_status="indexed",
        chunks=[
            Chunk(
                chunk_id=f"{doc_id}_c1",
                document_id=doc_id,
                source="Test_Handbook.pdf",
                page=1,
                text="Attendance requirement is 75% for all students.",
            )
        ],
    )
    save_document(doc_meta)

    knowledge = generate_document_knowledge(doc_id)
    md = export_knowledge_as_markdown(knowledge)
    assert "# Test_Handbook.pdf" in md
    assert "## Overview" in md
    assert "## Knowledge Categories" in md
    assert "## Key Information" in md


def test_api_get_document_knowledge():
    doc_id = "test_doc_api_knowledge"
    doc_meta = DocumentMetadata(
        document_id=doc_id,
        filename="API_Doc.pdf",
        stored_filename=f"{doc_id}_API.pdf",
        file_size_bytes=2048,
        pages=2,
        chunks_count=1,
        created_at="2026-10-06T12:00:00Z",
        status="processed",
        indexing_status="indexed",
        chunks=[
            Chunk(
                chunk_id=f"{doc_id}_c1",
                document_id=doc_id,
                source="API_Doc.pdf",
                page=1,
                text="75% minimum attendance required to appear for examinations.",
            )
        ],
    )
    save_document(doc_meta)

    resp = client.get(f"/documents/{doc_id}/knowledge")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == doc_id
    assert data["filename"] == "API_Doc.pdf"
    assert "categories" in data
    assert "key_information" in data
    assert "suggested_questions" in data

    # Test export endpoint
    export_resp = client.get(f"/documents/{doc_id}/knowledge/export/markdown")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["document_id"] == doc_id
    assert "# API_Doc.pdf" in export_data["markdown"]


def test_api_get_nonexistent_document_knowledge():
    resp = client.get("/documents/nonexistent_doc_id_999999/knowledge")
    assert resp.status_code == 404
