import os
import sys
import tempfile
import pymupdf as fitz
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.document import PageExtraction
from app.services.chunker import chunk_document_pages, chunk_page_text
from app.services.pdf_processor import (
    CorruptedPDFError,
    EmptyPDFError,
    ScannedPDFError,
    extract_text_from_pdf,
)
from app.services.text_cleaner import clean_text


def create_sample_pdf(pages_text: list[str]) -> bytes:
    """Helper to create a test PDF in-memory using PyMuPDF."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((50, 72), text)
        else:
            # Draw a shape to make it a valid PDF page without text
            page.draw_rect(fitz.Rect(10, 10, 50, 50), color=(0, 0, 1))
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ==============================================================================
# 1. Text Cleaner Tests
# ==============================================================================

def test_clean_text_normalizes_whitespace():
    raw = "This   is    a   test   with    multiple   spaces."
    cleaned = clean_text(raw)
    assert cleaned == "This is a test with multiple spaces."


def test_clean_text_removes_unnecessary_linebreaks_within_paragraph():
    raw = "The quick brown fox\njumps over the\nlazy dog."
    cleaned = clean_text(raw)
    assert cleaned == "The quick brown fox jumps over the lazy dog."


def test_clean_text_preserves_paragraph_boundaries():
    raw = "First paragraph content here.\n\n\n\nSecond paragraph content here."
    cleaned = clean_text(raw)
    assert cleaned == "First paragraph content here.\n\nSecond paragraph content here."


def test_clean_text_removes_artifacts_and_soft_hyphens():
    raw = "Arti\x00fact removal and docu-\nmentation test\x0c."
    cleaned = clean_text(raw)
    assert "\x00" not in cleaned
    assert "\x0c" not in cleaned
    assert "documentation test" in cleaned


def test_clean_text_preserves_list_items():
    raw = "Rules:\n- Item one\n- Item two\n- Item three"
    cleaned = clean_text(raw)
    assert "- Item one" in cleaned
    assert "- Item two" in cleaned
    assert "- Item three" in cleaned


# ==============================================================================
# 2. Chunker Tests
# ==============================================================================

def test_chunk_page_text_short_text():
    text = "Short text that easily fits in one chunk."
    chunks = chunk_page_text(
        text=text,
        document_id="doc_test",
        source="handbook.pdf",
        page=1,
        chunk_size=200,
        chunk_overlap=50,
    )
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc_test_page1_chunk1"
    assert chunks[0].page == 1
    assert chunks[0].document_id == "doc_test"
    assert chunks[0].source == "handbook.pdf"
    assert chunks[0].text == text


def test_chunk_page_text_splits_long_text_with_overlap():
    # Construct a long text with distinct sentences
    sentence = "LocalDoc AI provides private local document search without cloud APIs. "
    long_text = sentence * 15  # ~1065 characters

    chunk_size = 300
    chunk_overlap = 60

    chunks = chunk_page_text(
        text=long_text,
        document_id="doc_long",
        source="privacy.pdf",
        page=3,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    # Must be split into multiple chunks
    assert len(chunks) > 1

    # Verify metadata on all chunks
    for i, chunk in enumerate(chunks, start=1):
        assert chunk.chunk_id == f"doc_long_page3_chunk{i}"
        assert chunk.document_id == "doc_long"
        assert chunk.source == "privacy.pdf"
        assert chunk.page == 3
        assert len(chunk.text) > 0

    # Verify overlap: some tail text of chunk 0 appears in chunk 1
    chunk0_words = chunks[0].text.split()[-3:]
    overlap_phrase = " ".join(chunk0_words)
    assert overlap_phrase in chunks[1].text


def test_chunk_document_pages_multi_page():
    pages = [
        PageExtraction(page=1, text="Page 1 content about admission.", source="guide.pdf", has_text=True),
        PageExtraction(page=2, text="Page 2 content about curriculum.", source="guide.pdf", has_text=True),
        PageExtraction(page=3, text="", source="guide.pdf", has_text=False),  # Blank page
    ]
    chunks = chunk_document_pages(pages, document_id="doc_multi", chunk_size=200, chunk_overlap=40)
    assert len(chunks) == 2
    assert chunks[0].page == 1
    assert chunks[0].chunk_id == "doc_multi_page1_chunk1"
    assert chunks[1].page == 2
    assert chunks[1].chunk_id == "doc_multi_page2_chunk1"


# ==============================================================================
# 3. PDF Text Extraction & Error Handling Tests
# ==============================================================================

def test_extract_text_valid_multi_page_pdf():
    pdf_bytes = create_sample_pdf([
        "First page attendance requirements.",
        "Second page exam grading schedule.",
    ])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        pages = extract_text_from_pdf(tmp_path, "sample.pdf")
        assert len(pages) == 2
        assert pages[0].page == 1
        assert "attendance requirements" in pages[0].text
        assert pages[0].source == "sample.pdf"
        assert pages[0].has_text is True

        assert pages[1].page == 2
        assert "exam grading schedule" in pages[1].text
        assert pages[1].source == "sample.pdf"
        assert pages[1].has_text is True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_extract_text_scanned_pdf_raises_error():
    # PDF with blank/drawing pages and no extractable text
    pdf_bytes = create_sample_pdf(["", ""])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        with pytest.raises(ScannedPDFError) as exc_info:
            extract_text_from_pdf(tmp_path, "scanned.pdf")
        assert "OCR are not currently supported" in str(exc_info.value)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_extract_text_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with pytest.raises(EmptyPDFError):
            extract_text_from_pdf(tmp_path, "empty.pdf")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_extract_text_corrupted_file():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\nCorrupted binary rubbish")
        tmp_path = tmp.name

    try:
        with pytest.raises(CorruptedPDFError):
            extract_text_from_pdf(tmp_path, "corrupted.pdf")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
