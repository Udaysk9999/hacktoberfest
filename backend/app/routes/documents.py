from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
from typing import List, Optional
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

from app.config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL_NAME,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    UPLOAD_DIR,
)
from app.models.document import (
    Chunk,
    DocumentKnowledgeResponse,
    DocumentMetadata,
    DocumentSection,
    DocumentStructureResponse,
    DocumentUploadResponse,
)
from app.models.search import (
    IndexRequest,
    IndexResponse,
)
from app.services.chunker import chunk_document_pages
from app.services.embeddings import generate_embeddings
from app.services.pdf_processor import (
    CorruptedPDFError,
    EmptyPDFError,
    PasswordProtectedPDFError,
    ScannedPDFError,
    extract_text_from_pdf,
)
from app.services.storage import (
    compute_content_hash,
    find_document_by_content,
    find_document_by_content_hash,
    generate_display_title,
    get_chunks,
    get_document,
    list_documents,
    save_document,
    save_uploaded_pdf,
)
from app.services.structure_detector import get_or_create_document_structure
from app.services.knowledge_service import (
    generate_document_knowledge,
    get_stored_knowledge,
    export_knowledge_as_markdown,
)
from app.services.vector_store import get_vector_store

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

    # 4. Content-based deduplication check (SHA-256)
    content_hash = compute_content_hash(content)
    existing_doc = find_document_by_content_hash(content_hash)
    if existing_doc:
        existing_doc.duplicate_count = getattr(existing_doc, "duplicate_count", 1) + 1
        save_document(existing_doc)
        logger.info(f"Duplicate upload detected: {existing_doc.document_id} for '{original_filename}'. Reusing existing.")
        return DocumentUploadResponse(
            document_id=existing_doc.document_id,
            filename=existing_doc.filename,
            display_title=existing_doc.display_title or generate_display_title(existing_doc.filename),
            stored_filename=existing_doc.stored_filename,
            pages=existing_doc.pages,
            chunks=existing_doc.chunks_count,
            status="already_exists",
            indexing_status=existing_doc.indexing_status,
            message=f"Document '{existing_doc.filename}' already exists in your knowledge base.",
        )

    # 5. Generate secure identifiers and filenames
    doc_id = f"doc_{content_hash[:12]}"
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

    # Secondary deduplication check by extracted text fingerprint
    chunk_texts = [c.text for c in chunks]
    existing_by_text = find_document_by_content(content, original_filename, len(extracted_pages), chunk_texts)
    if existing_by_text:
        if saved_pdf_path.exists():
            saved_pdf_path.unlink()
        existing_by_text.duplicate_count = getattr(existing_by_text, "duplicate_count", 1) + 1
        save_document(existing_by_text)
        return DocumentUploadResponse(
            document_id=existing_by_text.document_id,
            filename=existing_by_text.filename,
            display_title=existing_by_text.display_title or generate_display_title(existing_by_text.filename),
            stored_filename=existing_by_text.stored_filename,
            pages=existing_by_text.pages,
            chunks=existing_by_text.chunks_count,
            status="already_exists",
            indexing_status=existing_by_text.indexing_status,
            message=f"Document '{existing_by_text.filename}' already exists in your knowledge base.",
        )

    # 9. Save document metadata and chunks
    now_iso = datetime.now(timezone.utc).isoformat()
    display_title = generate_display_title(original_filename)
    metadata = DocumentMetadata(
        document_id=doc_id,
        filename=original_filename,
        display_title=display_title,
        stored_filename=stored_filename,
        file_size_bytes=file_size,
        pages=len(extracted_pages),
        chunks_count=len(chunks),
        created_at=now_iso,
        status="processed",
        indexing_status="pending",
        content_hash=content_hash,
        duplicate_count=1,
        chunks=chunks,
    )

    try:
        save_document(metadata)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist document chunks: {str(e)}",
        )

    # 10. Automatically index chunks into local FAISS vector store
    indexing_status = "indexed"
    if chunks:
        try:
            chunk_texts = [c.text for c in chunks]
            embeddings = generate_embeddings(chunk_texts)
            vector_store = get_vector_store()
            vector_store.add_chunks(
                chunks=chunks,
                embeddings=embeddings,
                document_id=doc_id,
            )
            metadata.indexing_status = "indexed"
            save_document(metadata)
        except Exception as e:
            logger.error(f"Failed to automatically index chunks for document '{doc_id}': {e}")
            indexing_status = "failed"
            metadata.indexing_status = "failed"
            try:
                save_document(metadata)
            except Exception:
                pass

    # 11. Pre-generate document structure
    try:
        get_or_create_document_structure(doc_id)
    except Exception as e:
        logger.warning(f"Could not pre-generate structure for '{doc_id}': {e}")

    # 12. Pre-generate knowledge classification
    try:
        generate_document_knowledge(doc_id)
    except Exception as e:
        logger.warning(f"Could not pre-generate knowledge for '{doc_id}': {e}")

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=original_filename,
        display_title=display_title,
        stored_filename=stored_filename,
        pages=len(extracted_pages),
        chunks=len(chunks),
        status="processed",
        indexing_status=indexing_status,
        message="Document uploaded and indexed successfully.",
    )


@router.get(
    "/stats",
    summary="Get aggregate knowledge base statistics",
)
def get_knowledge_base_stats():
    """Retrieve aggregate statistics about the local knowledge base and vector index."""
    docs = list_documents()
    vector_store = get_vector_store()
    total_pages = sum(d.pages for d in docs)
    total_chunks = sum(d.chunks_count for d in docs)
    indexed_docs = sum(1 for d in docs if vector_store.is_document_indexed(d.document_id))
    return {
        "total_documents": len(docs),
        "total_indexed_documents": indexed_docs,
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "total_indexed_vectors": vector_store.index.ntotal,
        "ready": vector_store.index.ntotal > 0,
    }


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
    "/{document_id}/structure",
    response_model=DocumentStructureResponse,
    summary="Get detected document structure and section page ranges",
)
def get_document_structure(document_id: str):
    """Retrieve detected sections and page ranges for a processed document."""
    structure = get_or_create_document_structure(document_id)
    if not structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return structure


@router.get(
    "/{document_id}/knowledge",
    response_model=DocumentKnowledgeResponse,
    summary="Get structured knowledge, categories, topics, key facts, and questions",
)
def get_document_knowledge_endpoint(document_id: str):
    """Retrieve or generate persistent grounded knowledge for a document."""
    knowledge = generate_document_knowledge(document_id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return knowledge


@router.get(
    "/{document_id}/knowledge/export/markdown",
    summary="Export structured knowledge as Markdown",
)
def export_document_knowledge_markdown(document_id: str):
    """Export grounded document knowledge formatted in clean Markdown."""
    knowledge = generate_document_knowledge(document_id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    md_content = export_knowledge_as_markdown(knowledge)
    return {
        "document_id": document_id,
        "filename": knowledge.filename,
        "markdown": md_content,
    }


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
    """List all processed documents in local storage with indexing status."""
    docs = list_documents()
    vector_store = get_vector_store()
    return [
        {
            "document_id": d.document_id,
            "filename": d.filename,
            "display_title": getattr(d, "display_title", None) or generate_display_title(d.filename),
            "stored_filename": d.stored_filename,
            "pages": d.pages,
            "chunks": d.chunks_count,
            "chunks_count": d.chunks_count,
            "created_at": d.created_at,
            "upload_timestamp": d.created_at,
            "status": d.status,
            "processing_status": d.status,
            "indexing_status": getattr(d, "indexing_status", None) or ("indexed" if vector_store.is_document_indexed(d.document_id) else "pending"),
            "file_size_bytes": d.file_size_bytes,
            "content_hash": getattr(d, "content_hash", None),
            "duplicate_count": getattr(d, "duplicate_count", 1),
        }
        for d in docs
    ]


@router.post(
    "/index",
    response_model=IndexResponse,
    summary="Index processed document chunks into FAISS vector store",
)
def index_documents(request: Optional[IndexRequest] = None):
    """
    Generate embeddings and index processed document chunks into FAISS.
    Avoids re-indexing already indexed documents unless reindex=True.
    """
    req = request or IndexRequest()
    vector_store = get_vector_store()

    docs_to_index: list[DocumentMetadata] = []
    if req.document_id:
        doc = get_document(req.document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{req.document_id}' not found.",
            )
        docs_to_index.append(doc)
    else:
        all_docs = list_documents()
        for doc in all_docs:
            if req.reindex or not vector_store.is_document_indexed(doc.document_id):
                docs_to_index.append(doc)

    indexed_chunks_total = 0
    indexed_docs_total = 0

    for doc in docs_to_index:
        chunks = doc.chunks
        if not chunks:
            continue
        try:
            chunk_texts = [c.text for c in chunks]
            embeddings = generate_embeddings(chunk_texts)
            count = vector_store.add_chunks(
                chunks=chunks,
                embeddings=embeddings,
                document_id=doc.document_id,
                reindex=req.reindex,
            )
            if count > 0:
                indexed_chunks_total += count
                indexed_docs_total += 1
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate embeddings for document '{doc.document_id}': {str(e)}",
            )

    return IndexResponse(
        status="indexed",
        indexed_documents=indexed_docs_total,
        indexed_chunks=indexed_chunks_total,
        total_vectors_in_index=vector_store.index.ntotal,
        embedding_model=EMBEDDING_MODEL_NAME,
    )


@router.post(
    "/{document_id}/index",
    response_model=IndexResponse,
    summary="Index a specific document by ID",
)
def index_single_document(document_id: str, reindex: bool = False):
    """Convenience endpoint to index a specific document by its ID."""
    return index_documents(IndexRequest(document_id=document_id, reindex=reindex))


@router.post(
    "/reset",
    summary="Reset local FAISS index and metadata",
)
def reset_vector_store():
    """
    Safely reset the local FAISS vector index and chunk metadata mapping.
    Does not delete raw uploaded PDFs or processed documents JSONs.
    """
    vector_store = get_vector_store()
    vector_store.clear()
    return {
        "status": "reset",
        "total_vectors": 0,
        "indexed_documents": 0,
    }
