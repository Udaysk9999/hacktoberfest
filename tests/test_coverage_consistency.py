import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pymupdf as fitz
from pathlib import Path
from app.config import PROCESSED_DATA_DIR, FAISS_DIR
from app.models.document import DocumentMetadata
from app.services.chunker import chunk_document_pages
from app.services.embeddings import generate_embeddings
from app.services.pdf_processor import extract_text_from_pdf
from app.services.storage import list_documents
from app.services.vector_store import FaissVectorStore


def test_faiss_vector_count_matches_metadata_records():
    """Verify FAISS vector count matches metadata chunk count in the persistent store."""
    vs = FaissVectorStore()
    if vs.index.ntotal > 0:
        assert vs.index.ntotal == len(vs.id_to_metadata), (
            f"Mismatch: FAISS index has {vs.index.ntotal} vectors, "
            f"but metadata store has {len(vs.id_to_metadata)} records."
        )


def test_every_indexed_chunk_has_valid_metadata_fields():
    """Verify that every indexed chunk in the FAISS metadata store has valid fields."""
    vs = FaissVectorStore()
    if vs.index.ntotal > 0:
        for vec_id, meta in vs.id_to_metadata.items():
            assert isinstance(vec_id, int), f"Vector ID must be integer, got {vec_id}"
            assert "chunk_id" in meta and meta["chunk_id"], f"Missing chunk_id in vector {vec_id}"
            assert "document_id" in meta and meta["document_id"], f"Missing document_id in vector {vec_id}"
            assert "source" in meta and meta["source"], f"Missing source in vector {vec_id}"
            assert "page" in meta and isinstance(meta["page"], int) and meta["page"] >= 1, (
                f"Invalid page {meta.get('page')} in vector {vec_id}"
            )
            assert "text" in meta and meta["text"].strip(), f"Empty text in vector {vec_id}"


def test_processed_documents_page_and_chunk_consistency():
    """Verify that all processed document JSON records have consistent pages and chunks."""
    documents = list_documents()
    for doc in documents:
        assert doc.pages >= 1, f"Document {doc.document_id} has invalid page count: {doc.pages}"
        assert doc.chunks_count == len(doc.chunks), (
            f"Document {doc.document_id} chunks_count mismatch: "
            f"{doc.chunks_count} vs len {len(doc.chunks)}"
        )
        for chunk in doc.chunks:
            assert chunk.document_id == doc.document_id
            assert chunk.source == doc.filename
            assert 1 <= chunk.page <= doc.pages
            assert len(chunk.text.strip()) > 0


def test_synthetic_document_coverage_consistency(tmp_path):
    """
    Test full document coverage on a synthetic multi-page PDF:
    Verify extracted pages == PDF pages,
    every page with text produces chunks,
    embedding count == chunk count,
    FAISS vector count == metadata chunk count.
    """
    # 1. Create a 3-page synthetic PDF
    pdf_path = tmp_path / "test_doc_coverage.pdf"
    doc = fitz.open()
    for i in range(1, 4):
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            (50, 72),
            f"Chapter {i}: Detailed section on academic regulations for term {i}.\n"
            f"Students must complete all required modules by week {i * 4}.\n"
            f"Failure to meet this standard will require formal committee review.",
            fontsize=12,
        )
    doc.save(str(pdf_path))
    doc.close()

    # 2. Extract text from all pages
    pages = extract_text_from_pdf(pdf_path, "test_doc_coverage.pdf")
    assert len(pages) == 3, f"Expected 3 extracted pages, got {len(pages)}"
    assert all(p.has_text for p in pages), "All pages should have usable text"

    # 3. Chunk entire document
    chunks = chunk_document_pages(pages, document_id="doc_coverage_test")
    assert len(chunks) >= 3, f"Expected at least 3 chunks (one per page), got {len(chunks)}"

    # Check page distribution
    pages_in_chunks = {c.page for c in chunks}
    assert pages_in_chunks == {1, 2, 3}, f"Chunks should cover all pages: {pages_in_chunks}"

    # 4. Generate embeddings and index in isolated vector store
    chunk_texts = [c.text for c in chunks]
    embeddings = generate_embeddings(chunk_texts)
    assert len(embeddings) == len(chunks), "Embedding count must equal chunk count"

    store = FaissVectorStore(
        index_path=tmp_path / "test.faiss",
        metadata_path=tmp_path / "test_meta.json",
    )
    indexed_count = store.add_chunks(chunks, embeddings, "doc_coverage_test")
    assert indexed_count == len(chunks)
    assert store.index.ntotal == len(chunks)
    assert len(store.id_to_metadata) == len(chunks)

    # 5. Verify every chunk's metadata is preserved
    for idx, chunk in enumerate(chunks):
        meta = store.id_to_metadata[idx]
        assert meta["chunk_id"] == chunk.chunk_id
        assert meta["document_id"] == "doc_coverage_test"
        assert meta["source"] == "test_doc_coverage.pdf"
        assert meta["page"] == chunk.page
        assert meta["text"] == chunk.text
