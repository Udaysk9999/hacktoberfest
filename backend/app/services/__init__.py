"""LocalDoc AI application services."""
from app.services.chunker import chunk_document_pages, chunk_page_text
from app.services.pdf_processor import (
    CorruptedPDFError,
    EmptyPDFError,
    PasswordProtectedPDFError,
    PDFProcessingError,
    ScannedPDFError,
    extract_text_from_pdf,
)
from app.services.storage import (
    get_chunks,
    get_document,
    list_documents,
    save_document,
    save_uploaded_pdf,
)
from app.services.text_cleaner import clean_text

__all__ = [
    "clean_text",
    "extract_text_from_pdf",
    "chunk_document_pages",
    "chunk_page_text",
    "save_uploaded_pdf",
    "save_document",
    "get_document",
    "get_chunks",
    "list_documents",
    "PDFProcessingError",
    "PasswordProtectedPDFError",
    "EmptyPDFError",
    "ScannedPDFError",
    "CorruptedPDFError",
]
