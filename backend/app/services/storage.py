import json
from pathlib import Path
from typing import List, Optional

from app.config import PROCESSED_DATA_DIR, UPLOAD_DIR
from app.models.document import Chunk, DocumentMetadata


def save_uploaded_pdf(content: bytes, filename: str) -> Path:
    """Save raw PDF bytes to the local uploads directory."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / filename
    destination.write_bytes(content)
    return destination


def save_document(metadata: DocumentMetadata) -> Path:
    """Save processed document metadata and chunks as a JSON record."""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination = PROCESSED_DATA_DIR / f"{metadata.document_id}.json"
    with open(destination, "w", encoding="utf-8") as f:
        json.dump(metadata.model_dump(), f, indent=2, ensure_ascii=False)
    return destination


def get_document(document_id: str) -> Optional[DocumentMetadata]:
    """Retrieve document metadata and chunks by document ID."""
    file_path = PROCESSED_DATA_DIR / f"{document_id}.json"
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return DocumentMetadata(**data)
    except Exception:
        return None


def get_chunks(document_id: str) -> Optional[List[Chunk]]:
    """Retrieve all chunks for a specific document."""
    doc = get_document(document_id)
    if doc is None:
        return None
    return doc.chunks


def list_documents() -> List[DocumentMetadata]:
    """List all locally processed documents."""
    if not PROCESSED_DATA_DIR.exists():
        return []

    documents = []
    for file_path in PROCESSED_DATA_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            documents.append(DocumentMetadata(**data))
        except Exception:
            continue
    return sorted(documents, key=lambda d: d.created_at, reverse=True)
