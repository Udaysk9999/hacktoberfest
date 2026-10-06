import io
import os
import sys
import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app

client = TestClient(app)


def generate_test_pdf_bytes(pages: list[str]) -> bytes:
    """Generate in-memory PDF bytes using PyMuPDF."""
    doc = fitz.open()
    for text in pages:
        p = doc.new_page()
        if text:
            p.insert_text((50, 72), text)
        else:
            p.draw_rect(fitz.Rect(10, 10, 50, 50), color=(1, 0, 0))
    b = doc.tobytes()
    doc.close()
    return b


def test_upload_valid_pdf_success():
    pdf_bytes = generate_test_pdf_bytes([
        "Page 1: Welcome to the University Handbook. All students must attend 75% of classes.",
        "Page 2: Examination regulations and grading criteria.",
    ])

    files = {
        "file": ("College_Handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }

    response = client.post("/documents/upload", files=files)
    assert response.status_code == 201

    data = response.json()
    assert "document_id" in data
    assert data["filename"] == "College_Handbook.pdf"
    assert data["stored_filename"].endswith(".pdf")
    assert data["pages"] == 2
    assert data["chunks"] >= 2
    # Accept both first-time upload ("processed") and dedup hit ("already_exists")
    assert data["status"] in ("processed", "already_exists")

    doc_id = data["document_id"]

    # Verify retrieval endpoint
    doc_resp = client.get(f"/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert doc_data["document_id"] == doc_id
    assert len(doc_data["chunks"]) == data["chunks"]

    # Verify chunks endpoint
    chunks_resp = client.get(f"/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks_data = chunks_resp.json()
    assert chunks_data["count"] == data["chunks"]

    # Verify chunk structure
    first_chunk = chunks_data["chunks"][0]
    assert first_chunk["document_id"] == doc_id
    assert first_chunk["source"] == "College_Handbook.pdf"
    assert first_chunk["page"] == 1
    assert "Welcome to the University Handbook" in first_chunk["text"]


def test_upload_rejects_non_pdf_extension():
    files = {
        "file": ("notes.txt", io.BytesIO(b"Hello world"), "text/plain")
    }
    response = client.post("/documents/upload", files=files)
    assert response.status_code == 400
    assert "Only .pdf files are accepted" in response.json()["detail"]


def test_upload_rejects_empty_file():
    files = {
        "file": ("empty.pdf", io.BytesIO(b""), "application/pdf")
    }
    response = client.post("/documents/upload", files=files)
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_upload_rejects_corrupted_header():
    files = {
        "file": ("fake.pdf", io.BytesIO(b"Not a real PDF file header"), "application/pdf")
    }
    response = client.post("/documents/upload", files=files)
    assert response.status_code == 400
    assert "header does not match" in response.json()["detail"]


def test_upload_scanned_pdf_returns_ocr_message():
    # PDF with no text on any page
    pdf_bytes = generate_test_pdf_bytes(["", ""])

    files = {
        "file": ("scanned_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }
    response = client.post("/documents/upload", files=files)
    assert response.status_code == 422
    assert "OCR are not currently supported" in response.json()["detail"]


def test_get_nonexistent_document():
    response = client.get("/documents/doc_nonexistent_123")
    assert response.status_code == 404
