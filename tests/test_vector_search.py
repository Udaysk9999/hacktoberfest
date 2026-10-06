import os
import sys
import tempfile
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.models.document import Chunk, DocumentMetadata
from app.models.search import SearchRequest
from app.services.embeddings import (
    generate_embeddings,
    generate_query_embedding,
)
from app.services.storage import save_document
from app.services.vector_store import FaissVectorStore, get_vector_store

client = TestClient(app)


# ==============================================================================
# 1. Embedding Tests
# ==============================================================================

def test_embeddings_generation_and_dimensions():
    texts = [
        "Attendance requirement for college students is 75%.",
        "Library opening hours are 8am to 8pm daily.",
    ]
    embeddings = generate_embeddings(texts)

    # 1. Dimensions are consistent (384 for all-MiniLM-L6-v2)
    assert embeddings.shape == (2, 384)
    assert embeddings.dtype == np.float32

    # 2. Check normalization (L2 norm should be ~ 1.0)
    norms = np.linalg.norm(embeddings, axis=1)
    for norm in norms:
        assert abs(norm - 1.0) < 1e-4

    # 3. Query embedding
    q_emb = generate_query_embedding("What is the attendance policy?")
    assert q_emb.shape == (384,)
    assert abs(np.linalg.norm(q_emb) - 1.0) < 1e-4


# ==============================================================================
# 2. FAISS Index & Metadata Association Tests
# ==============================================================================

def test_faiss_index_creation_and_insertion():
    with tempfile.TemporaryDirectory() as tmp_dir:
        index_file = Path(tmp_dir) / "test.faiss"
        meta_file = Path(tmp_dir) / "test_meta.json"

        store = FaissVectorStore(dimension=384, index_path=index_file, metadata_path=meta_file)
        assert store.index.ntotal == 0

        chunks = [
            Chunk(
                chunk_id="doc1_page1_chunk1",
                document_id="doc1",
                source="College_Handbook.pdf",
                page=1,
                text="Students must maintain 75% attendance.",
            ),
            Chunk(
                chunk_id="doc1_page2_chunk1",
                document_id="doc1",
                source="College_Handbook.pdf",
                page=2,
                text="Exam registration closes on Friday.",
            ),
        ]
        embs = generate_embeddings([c.text for c in chunks])

        added = store.add_chunks(chunks=chunks, embeddings=embs, document_id="doc1")
        assert added == 2
        assert store.index.ntotal == 2

        # Verify metadata mapping
        assert 0 in store.id_to_metadata
        assert 1 in store.id_to_metadata
        assert store.id_to_metadata[0]["chunk_id"] == "doc1_page1_chunk1"
        assert store.id_to_metadata[0]["source"] == "College_Handbook.pdf"
        assert store.id_to_metadata[0]["page"] == 1
        assert store.id_to_metadata[1]["page"] == 2


def test_semantic_query_retrieval_and_metadata_preservation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        index_file = Path(tmp_dir) / "test.faiss"
        meta_file = Path(tmp_dir) / "test_meta.json"

        store = FaissVectorStore(dimension=384, index_path=index_file, metadata_path=meta_file)

        chunks = [
            Chunk(
                chunk_id="doc1_page12_chunk1",
                document_id="doc1",
                source="College_Handbook.pdf",
                page=12,
                text="The minimum mandatory attendance requirement for all courses is 75% of scheduled lectures.",
            ),
            Chunk(
                chunk_id="doc1_page20_chunk1",
                document_id="doc1",
                source="College_Handbook.pdf",
                page=20,
                text="The campus cafeteria provides meals and snacks between 7:00 AM and 9:00 PM.",
            ),
        ]
        embs = generate_embeddings([c.text for c in chunks])
        store.add_chunks(chunks=chunks, embeddings=embs, document_id="doc1")

        # Query specifically about attendance
        q_emb = generate_query_embedding("What percentage of attendance is required?")
        results = store.search(q_emb, top_k=2)

        assert len(results) == 2
        # Top result must be the attendance chunk
        top = results[0]
        assert top.chunk_id == "doc1_page12_chunk1"
        assert top.source == "College_Handbook.pdf"
        assert top.page == 12
        assert "75% of scheduled lectures" in top.text
        assert top.score > results[1].score


def test_multiple_documents_indexing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        index_file = Path(tmp_dir) / "test.faiss"
        meta_file = Path(tmp_dir) / "test_meta.json"

        store = FaissVectorStore(dimension=384, index_path=index_file, metadata_path=meta_file)

        doc1_chunks = [
            Chunk(
                chunk_id="doc1_page1_chunk1",
                document_id="doc1",
                source="College_Handbook.pdf",
                page=1,
                text="Hostel curfew is 10:00 PM on weekdays.",
            )
        ]
        doc2_chunks = [
            Chunk(
                chunk_id="doc2_page5_chunk1",
                document_id="doc2",
                source="Scholarship_Guidelines.pdf",
                page=5,
                text="Merit scholarships cover 100% of tuition fees for students with GPA above 3.8.",
            )
        ]

        store.add_chunks(doc1_chunks, generate_embeddings([c.text for c in doc1_chunks]), "doc1")
        store.add_chunks(doc2_chunks, generate_embeddings([c.text for c in doc2_chunks]), "doc2")

        assert store.index.ntotal == 2
        assert "doc1" in store.indexed_doc_ids
        assert "doc2" in store.indexed_doc_ids

        # Search scholarship info
        q_emb = generate_query_embedding("How do I get a merit scholarship for tuition?")
        results = store.search(q_emb, top_k=1)
        assert len(results) == 1
        assert results[0].document_id == "doc2"
        assert results[0].source == "Scholarship_Guidelines.pdf"
        assert results[0].page == 5


def test_index_persistence_and_reload():
    with tempfile.TemporaryDirectory() as tmp_dir:
        index_file = Path(tmp_dir) / "test.faiss"
        meta_file = Path(tmp_dir) / "test_meta.json"

        # 1. Initialize store and add chunk
        store1 = FaissVectorStore(dimension=384, index_path=index_file, metadata_path=meta_file)
        chunks = [
            Chunk(
                chunk_id="doc_persist_chunk1",
                document_id="doc_persist",
                source="Persistent_Handbook.pdf",
                page=7,
                text="Final examinations are held in December and May.",
            )
        ]
        store1.add_chunks(chunks, generate_embeddings([c.text for c in chunks]), "doc_persist")
        assert store1.index.ntotal == 1

        # 2. Simulate application restart by creating a new store instance pointing to same files
        store2 = FaissVectorStore(dimension=384, index_path=index_file, metadata_path=meta_file)
        assert store2.index.ntotal == 1
        assert "doc_persist" in store2.indexed_doc_ids

        # Search should work immediately on reloaded store without re-indexing
        q_emb = generate_query_embedding("When are final examinations conducted?")
        results = store2.search(q_emb, top_k=1)
        assert len(results) == 1
        assert results[0].chunk_id == "doc_persist_chunk1"
        assert results[0].page == 7


# ==============================================================================
# 3. Search and Index API Endpoint Tests
# ==============================================================================

def test_api_search_endpoint():
    # Setup test document in storage and index
    doc_id = "doc_api_test_01"
    chunks = [
        Chunk(
            chunk_id=f"{doc_id}_page1_chunk1",
            document_id=doc_id,
            source="Academic_Rules.pdf",
            page=1,
            text="Minimum passing grade for undergraduate courses is C minus.",
        )
    ]
    metadata = DocumentMetadata(
        document_id=doc_id,
        filename="Academic_Rules.pdf",
        stored_filename=f"{doc_id}_Academic_Rules.pdf",
        file_size_bytes=1024,
        pages=1,
        chunks_count=1,
        created_at="2026-10-06T10:00:00Z",
        status="processed",
        chunks=chunks,
    )
    save_document(metadata)

    # Index document via API
    index_resp = client.post("/documents/index", json={"document_id": doc_id, "reindex": True})
    assert index_resp.status_code == 200
    index_data = index_resp.json()
    assert index_data["status"] == "indexed"
    assert index_data["indexed_documents"] >= 1

    # Search via /search API
    search_resp = client.post("/search", json={"query": "What is the minimum passing grade?", "top_k": 3})
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["query"] == "What is the minimum passing grade?"
    assert len(search_data["results"]) >= 1

    top_result = search_data["results"][0]
    assert "passing grade" in top_result["text"]
    assert top_result["source"] == "Academic_Rules.pdf"
    assert top_result["page"] == 1
    assert "score" in top_result
    assert top_result["score"] > 0.0


def test_api_search_empty_query_rejected():
    response = client.post("/search", json={"query": "   ", "top_k": 5})
    assert response.status_code in [400, 422]
