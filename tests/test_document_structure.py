import os
import sys
import pytest
import pymupdf as fitz
from pathlib import Path

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from app.main import app
from app.models.document import DocumentStructureResponse
from app.services.structure_detector import (
    detect_structure_from_pdf,
    get_or_create_document_structure,
    load_all_structures,
    save_all_structures,
)

client = TestClient(app)


def test_pdf_with_numbered_headings(tmp_path):
    """Test structure detection on a PDF containing numbered section headings."""
    pdf_path = tmp_path / "numbered_doc.pdf"
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((50, 72), "1.1 Introduction to Research Ethics\nAll researchers must adhere to protocols.")

    p2 = doc.new_page()
    p2.insert_text((50, 72), "1.2 Institutional Review Board Guidelines\nProtocols must be reviewed annually.")

    p3 = doc.new_page()
    p3.insert_text((50, 72), "2.1 Conflict of Interest Disclosure\nAnnual declarations are mandatory.")

    doc.save(str(pdf_path))
    doc.close()

    res = detect_structure_from_pdf(pdf_path, total_pages=3, document_id="doc_num_01", filename="numbered_doc.pdf")
    assert res.has_structure is True
    assert len(res.sections) == 3
    assert res.sections[0].title.startswith("1.1")
    assert res.sections[0].start_page == 1
    assert res.sections[1].title.startswith("1.2")
    assert res.sections[1].start_page == 2
    assert res.sections[2].title.startswith("2.1")
    assert res.sections[2].start_page == 3


def test_pdf_with_chapter_headings(tmp_path):
    """Test structure detection on a PDF containing Chapter headings."""
    pdf_path = tmp_path / "chapters_doc.pdf"
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((50, 72), "CHAPTER 1: Principles of Academic Integrity\nStudents must uphold honesty.")

    p2 = doc.new_page()
    p2.insert_text((50, 72), "Chapter 1 discussion details and rules continue on this page.")

    p3 = doc.new_page()
    p3.insert_text((50, 72), "CHAPTER 2: Examination Conduct and Proctors\nProctors will inspect IDs at entrance.")

    p4 = doc.new_page()
    p4.insert_text((50, 72), "CHAPTER 3: Disciplinary Sanctions\nViolations will be referred to committee.")

    doc.save(str(pdf_path))
    doc.close()

    res = detect_structure_from_pdf(pdf_path, total_pages=4, document_id="doc_chap_01", filename="chapters_doc.pdf")
    assert res.has_structure is True
    assert len(res.sections) == 3
    assert "CHAPTER 1" in res.sections[0].title
    assert res.sections[0].start_page == 1
    assert res.sections[0].end_page == 2  # Page 1 to 2
    assert "CHAPTER 2" in res.sections[1].title
    assert res.sections[1].start_page == 3
    assert res.sections[1].end_page == 3
    assert "CHAPTER 3" in res.sections[2].title
    assert res.sections[2].start_page == 4
    assert res.sections[2].end_page == 4


def test_correct_page_numbers_and_ranges(tmp_path):
    """Verify that section page ranges span accurately between consecutive headings."""
    pdf_path = tmp_path / "range_test.pdf"
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((50, 72), "Section 10.1: Campus Dining Policies\nMeal plans are required for freshmen.")

    p2 = doc.new_page()
    p2.insert_text((50, 72), "Meal plan points rollover rules.")

    p3 = doc.new_page()
    p3.insert_text((50, 72), "Dietary accommodations and vegan choices.")

    p4 = doc.new_page()
    p4.insert_text((50, 72), "Section 10.2: Housing and Dormitory Safety\nQuiet hours commence at 10 PM.")

    p5 = doc.new_page()
    p5.insert_text((50, 72), "Guest policy and emergency exits.")

    doc.save(str(pdf_path))
    doc.close()

    res = detect_structure_from_pdf(pdf_path, total_pages=5, document_id="doc_range_01", filename="range_test.pdf")
    assert res.has_structure is True
    assert len(res.sections) == 2

    # Section 10.1 spans pages 1-3
    assert res.sections[0].start_page == 1
    assert res.sections[0].end_page == 3

    # Section 10.2 spans pages 4-5
    assert res.sections[1].start_page == 4
    assert res.sections[1].end_page == 5


def test_document_id_and_separation(tmp_path):
    """Verify that structures for distinct document IDs remain strictly separated."""
    pdf1 = tmp_path / "doc_a.pdf"
    d1 = fitz.open()
    p1 = d1.new_page()
    p1.insert_text((50, 72), "CHAPTER 1: Document A Alpha Subject\nContent for Alpha.")
    d1.save(str(pdf1))
    d1.close()

    pdf2 = tmp_path / "doc_b.pdf"
    d2 = fitz.open()
    p2 = d2.new_page()
    p2.insert_text((50, 72), "CHAPTER 1: Document B Beta Subject\nContent for Beta.")
    d2.save(str(pdf2))
    d2.close()

    res_a = detect_structure_from_pdf(pdf1, 1, "doc_id_aaa", "doc_a.pdf")
    res_b = detect_structure_from_pdf(pdf2, 1, "doc_id_bbb", "doc_b.pdf")

    assert res_a.document_id == "doc_id_aaa"
    assert res_b.document_id == "doc_id_bbb"
    assert "Alpha" in res_a.sections[0].title
    assert "Beta" in res_b.sections[0].title
    assert "Beta" not in res_a.sections[0].title


def test_structure_persistence(tmp_path):
    """Verify structure caching and persistence across restarts."""
    test_data = {
        "doc_persist_test": {
            "document_id": "doc_persist_test",
            "filename": "persisted_file.pdf",
            "total_pages": 10,
            "has_structure": True,
            "sections": [
                {
                    "id": "sec_1",
                    "title": "CHAPTER 1: Test Chapter",
                    "section_type": "chapter",
                    "start_page": 1,
                    "end_page": 10,
                }
            ],
        }
    }
    save_all_structures(test_data)
    loaded = load_all_structures()
    assert "doc_persist_test" in loaded
    assert loaded["doc_persist_test"]["sections"][0]["title"] == "CHAPTER 1: Test Chapter"


def test_unstructured_document_does_not_get_fake_sections(tmp_path):
    """Verify that a document without clear headings returns has_structure=False and empty sections."""
    pdf_path = tmp_path / "unstructured.pdf"
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 72), "This is just a random plain text letter with no chapters or numbered sections.")
    p2 = doc.new_page()
    p2.insert_text((50, 72), "Continued prose paragraph discussing general thoughts without any section titles.")
    doc.save(str(pdf_path))
    doc.close()

    res = detect_structure_from_pdf(pdf_path, total_pages=2, document_id="doc_plain", filename="unstructured.pdf")
    assert res.has_structure is False
    assert res.sections == []


def test_api_get_document_structure():
    """Verify GET /documents/{document_id}/structure endpoint."""
    # Test with College_Handbook_2026.pdf doc
    response = client.get("/documents/doc_98ff4f356c36/structure")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == "doc_98ff4f356c36"
    assert data["has_structure"] is True
    assert len(data["sections"]) >= 3
    assert data["sections"][0]["start_page"] == 1


def test_api_get_nonexistent_document_structure():
    """Verify 404 for non-existent document ID."""
    response = client.get("/documents/doc_nonexistent_99999/structure")
    assert response.status_code == 404
