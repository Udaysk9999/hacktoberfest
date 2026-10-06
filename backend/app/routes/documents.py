from datetime import datetime, timezone
import os
from pathlib import Path
import re
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    UPLOAD_DIR,
)
from app.models.document import (
    Chunk,
    DocumentMetadata,
    DocumentUploadResponse,
)
from app.services.chunker import chunk_document_pages
from app.services.pdf_processor import (
    CorruptedPDFError,
    EmptyPDFError,
    PasswordProtectedPDFError,
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

router = APIRouter(prefix="/documents", tags=["documents"])


def sanitize_filename(filename: str) -> str:
    """Sanitize the original filename to avoid path traversal and invalid characters."""
    base_name = Path(filename).name
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", base_name)
    if not cleaned.lower().endswith(".pdf"):
        cleaned += ".pdf"
    return cleaned


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a PDF document",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF document to upload and process")
):
    """
    Upload a PDF file, extract its text page-by-page, clean the content,
    and split it into semantic chunks with source and page metadata.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded. Please select a PDF file.",
        )

    # 1. Validate file extension
    original_filename = file.filename
    file_ext = os.path.splitext(original_filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file_ext}'. Only .pdf files are accepted.",
        )

    # 2. Validate MIME type if provided
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{content_type}'. Expected 'application/pdf'.",
        )

    # 3. Read content and enforce maximum file size
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}",
        )

    file_size = len(content)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded file is empty (0 bytes).",
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed size of {MAX_FILE_SIZE_MB} MB.",
        )

    # 4. Validate PDF magic bytes header (%PDF)
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file format. The file header does not match the PDF specification.",
        )

    # 5. Generate secure identifiers and filenames
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    safe_name = sanitize_filename(original_filename)
    stored_filename = f"{doc_id}_{safe_name}"

    # 6. Save raw PDF to local uploads directory
    try:
        saved_pdf_path = save_uploaded_pdf(content, stored_filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save document to storage: {str(e)}",
        )

    # 7. Extract text page-by-page using PyMuPDF
    try:
        extracted_pages = extract_text_from_pdf(
            file_path=saved_pdf_path,
            source_filename=original_filename,
        )
    except PasswordProtectedPDFError as e:
        # Clean up uploaded raw file if invalid
        if saved_pdf_path.exists():
            saved_pdf_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except ScannedPDFError as e:
        if saved_pdf_path.exists():
            saved_pdf_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except EmptyPDFError as e:
        if saved_pdf_path.exists():
            saved_pdf_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except CorruptedPDFError as e:
        if saved_pdf_path.exists():
            saved_pdf_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except Exception as e:
        if saved_pdf_path.exists():
            saved_pdf_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during PDF text extraction: {str(e)}",
        )

    # 8. Chunk pages deterministically
    chunks = chunk_document_pages(
        pages=extracted_pages,
        document_id=doc_id,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    # 9. Save document metadata and chunks
    now_iso = datetime.now(timezone.utc).isoformat()
    metadata = DocumentMetadata(
        document_id=doc_id,
        filename=original_filename,
        stored_filename=stored_filename,
        file_size_bytes=file_size,
        pages=len(extracted_pages),
        chunks_count=len(chunks),
        created_at=now_iso,
        status="processed",
        chunks=chunks,
    )

    try:
        save_document(metadata)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist document chunks: {str(e)}",
        )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=original_filename,
        stored_filename=stored_filename,
        pages=len(extracted_pages),
        chunks=len(chunks),
        status="processed",
    )


@router.get(
    "/{document_id}",
    response_model=DocumentMetadata,
    summary="Get document details and chunks",
)
def get_document_details(document_id: str):
    """Retrieve full metadata and text chunks for a processed document."""
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return doc


@router.get(
    "/{document_id}/chunks",
    summary="Get extracted chunks for a document",
)
def get_document_chunks(document_id: str):
    """Retrieve only the text chunks and their metadata for a processed document."""
    chunks = get_chunks(document_id)
    if chunks is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return {
        "document_id": document_id,
        "count": len(chunks),
        "chunks": chunks,
    }


@router.get(
    "",
    summary="List all processed documents",
)
def get_all_documents():
    """List all processed documents in local storage."""
    docs = list_documents()
    return [
        {
            "document_id": d.document_id,
            "filename": d.filename,
            "stored_filename": d.stored_filename,
            "pages": d.pages,
            "chunks": d.chunks_count,
            "created_at": d.created_at,
            "status": d.status,
        }
        for d in docs
    ]
