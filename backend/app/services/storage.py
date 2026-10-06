import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from app.config import PROCESSED_DATA_DIR, UPLOAD_DIR
from app.models.document import Chunk, DocumentMetadata

logger = logging.getLogger(__name__)

ARCHIVE_DIR = PROCESSED_DATA_DIR.parent / "processed_archive"


def compute_content_hash(content: bytes) -> str:
    """Calculate SHA-256 fingerprint for document content bytes."""
    return hashlib.sha256(content).hexdigest()


def compute_content_fingerprint(doc: DocumentMetadata) -> str:
    """
    Compute a reliable content fingerprint for a document record.
    Uses SHA-256 of raw file if present, otherwise normalized chunk texts and page count.
    """
    raw_path = UPLOAD_DIR / doc.stored_filename
    if raw_path.exists():
        try:
            return hashlib.sha256(raw_path.read_bytes()).hexdigest()
        except Exception:
            pass
    # Grounded fallback: normalized chunk text + page count + filename
    normalized_text = " ".join(c.text.strip() for c in doc.chunks)
    return hashlib.sha256(f"{doc.pages}_{doc.filename}_{normalized_text}".encode("utf-8")).hexdigest()


def generate_display_title(filename: str) -> str:
    """Generate a clean, readable display title while preserving vital numbers and dates."""
    stem = Path(filename).stem
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4]

    # Specific common handbooks
    if stem.lower() == "handbookfinalversion":
        return "Handbook Final Version"
    if stem.lower() in ("handbook2020-2021", "handbook2020_2021"):
        return "Handbook 2020–2021"

    # Replace separators with space
    cleaned = re.sub(r"[_\-\.]+", " ", stem)
    # Split camelCase and letter-digit boundaries
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"([a-zA-Z])(\d+)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(\d+)([a-zA-Z])", r"\1 \2", cleaned)

    words = cleaned.split()
    capitalized = []
    for w in words:
        if len(w) <= 2:
            capitalized.append(w.upper())
        elif w.isupper() and len(w) > 4:
            capitalized.append(w.capitalize())
        else:
            capitalized.append(w.capitalize() if not (w.isupper() or any(c.isdigit() for c in w)) else w)
    return " ".join(capitalized).strip() or "Untitled Document"


def save_uploaded_pdf(content: bytes, filename: str) -> Path:
    """Save raw PDF bytes to the local uploads directory."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / filename
    destination.write_bytes(content)
    return destination


def save_document(metadata: DocumentMetadata) -> Path:
    """Save processed document metadata and chunks as a JSON record."""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not metadata.display_title:
        metadata.display_title = generate_display_title(metadata.filename)
    destination = PROCESSED_DATA_DIR / f"{metadata.document_id}.json"
    with open(destination, "w", encoding="utf-8") as f:
        json.dump(metadata.model_dump(), f, indent=2, ensure_ascii=False)
    return destination


def get_document(document_id: str) -> Optional[DocumentMetadata]:
    """Retrieve document metadata and chunks by document ID."""
    file_path = PROCESSED_DATA_DIR / f"{document_id}.json"
    if not file_path.exists():
        archive_path = ARCHIVE_DIR / f"{document_id}.json"
        if archive_path.exists():
            file_path = archive_path
        else:
            return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        doc = DocumentMetadata(**data)
        if not doc.display_title:
            doc.display_title = generate_display_title(doc.filename)
        return doc
    except Exception:
        return None


def find_document_by_content_hash(content_hash: str) -> Optional[DocumentMetadata]:
    """Search active processed documents for one with matching content hash."""
    if not PROCESSED_DATA_DIR.exists():
        return None

    for file_path in PROCESSED_DATA_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            h = data.get("content_hash")
            if h and h == content_hash:
                doc = DocumentMetadata(**data)
                if not doc.display_title:
                    doc.display_title = generate_display_title(doc.filename)
                return doc
            elif not h:
                # Calculate from raw file or fingerprint
                doc = DocumentMetadata(**data)
                fp = compute_content_fingerprint(doc)
                if fp == content_hash:
                    doc.content_hash = fp
                    save_document(doc)
                    return doc
        except Exception:
            continue
    return None


def find_document_by_content(content_bytes: bytes, filename: str, pages: int, chunk_texts: List[str]) -> Optional[DocumentMetadata]:
    """
    Find existing document either by SHA-256 bytes or by extracted content fingerprint.
    Guarantees no duplicate documents even across dynamic creation dates.
    """
    raw_hash = compute_content_hash(content_bytes)
    doc_by_hash = find_document_by_content_hash(raw_hash)
    if doc_by_hash:
        return doc_by_hash

    # Secondary check: compare extracted chunk text and page count
    norm_text = " ".join(t.strip() for t in chunk_texts)
    text_fingerprint = hashlib.sha256(f"{pages}_{filename}_{norm_text}".encode("utf-8")).hexdigest()

    for doc in list_documents():
        doc_fp = compute_content_fingerprint(doc)
        if doc_fp == text_fingerprint or (doc.filename == filename and doc.pages == pages and " ".join(c.text.strip() for c in doc.chunks) == norm_text):
            return doc

    return None


def get_chunks(document_id: str) -> Optional[List[Chunk]]:
    """Retrieve all chunks for a specific document."""
    doc = get_document(document_id)
    if doc is None:
        return None
    return doc.chunks


def list_documents() -> List[DocumentMetadata]:
    """List all unique locally processed documents with clean display titles."""
    if not PROCESSED_DATA_DIR.exists():
        return []

    documents = []
    seen_fingerprints = set()

    for file_path in PROCESSED_DATA_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc = DocumentMetadata(**data)
            if not doc.display_title:
                doc.display_title = generate_display_title(doc.filename)

            fp = doc.content_hash or compute_content_fingerprint(doc)
            doc.content_hash = fp

            # In-memory deduplication safeguard
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)

            documents.append(doc)
        except Exception:
            continue
    return sorted(documents, key=lambda d: d.created_at, reverse=True)


def deduplicate_and_migrate_existing_documents() -> int:
    """
    Safely group existing documents by content fingerprint, designate canonical records,
    update display titles and duplicate counts, and safely archive non-canonical duplicates.
    """
    if not PROCESSED_DATA_DIR.exists():
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    all_files = list(PROCESSED_DATA_DIR.glob("*.json"))
    if not all_files:
        return 0

    records: List[Tuple[Path, DocumentMetadata]] = []
    for p in all_files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append((p, DocumentMetadata(**data)))
        except Exception:
            continue

    groups: Dict[str, List[Tuple[Path, DocumentMetadata]]] = {}
    for path, doc in records:
        fp = compute_content_fingerprint(doc)
        doc.content_hash = fp
        groups.setdefault(fp, []).append((path, doc))

    from app.services.vector_store import get_vector_store
    vs = get_vector_store()

    removed_count = 0
    for fp, group in groups.items():
        if len(group) == 1:
            path, doc = group[0]
            if not doc.display_title or not doc.content_hash:
                doc.display_title = generate_display_title(doc.filename)
                doc.content_hash = fp
                save_document(doc)
            continue

        # Select canonical record: prefer indexed in FAISS, then oldest
        canonical_idx = 0
        for idx, (path, doc) in enumerate(group):
            if vs.is_document_indexed(doc.document_id):
                canonical_idx = idx
                break

        canonical_path, canonical_doc = group[canonical_idx]
        canonical_doc.duplicate_count = len(group)
        canonical_doc.display_title = generate_display_title(canonical_doc.filename)
        canonical_doc.content_hash = fp

        # If any copy had 'indexed' status, set canonical to 'indexed'
        if any(d.indexing_status == "indexed" for _, d in group):
            canonical_doc.indexing_status = "indexed"

        save_document(canonical_doc)

        # Archive non-canonical copies
        for idx, (path, doc) in enumerate(group):
            if idx != canonical_idx:
                try:
                    archive_dest = ARCHIVE_DIR / path.name
                    path.replace(archive_dest)
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Could not archive duplicate {path.name}: {e}")

    logger.info(f"Deduplicated {removed_count} redundant records. Active unique documents: {len(groups)}.")
    return removed_count
