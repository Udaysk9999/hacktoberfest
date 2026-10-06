import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional
import pymupdf as fitz

from app.config import METADATA_DIR, UPLOAD_DIR
from app.models.document import DocumentSection, DocumentStructureResponse
from app.services.storage import get_document

logger = logging.getLogger(__name__)

DOCUMENT_STRUCTURES_FILE = METADATA_DIR / "document_structures.json"


def load_all_structures() -> Dict[str, dict]:
    """Load cached document structures from disk."""
    if not DOCUMENT_STRUCTURES_FILE.exists():
        return {}
    try:
        with open(DOCUMENT_STRUCTURES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read document structures file: {e}")
        return {}


def save_all_structures(structures: Dict[str, dict]) -> None:
    """Save all document structures to local disk."""
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DOCUMENT_STRUCTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(structures, f, indent=2, ensure_ascii=False)


def detect_structure_from_pdf(pdf_path: Path, total_pages: int, document_id: str, filename: str) -> DocumentStructureResponse:
    """
    Detect document structure using PyMuPDF TOC bookmarks or structural heading patterns.
    Does NOT invent chapter names; extracts strictly what exists in the document.
    """
    sections: List[DocumentSection] = []

    try:
        doc = fitz.open(str(pdf_path))
        pdf_page_count = doc.page_count
        if total_pages <= 0:
            total_pages = pdf_page_count

        # 1. First, check if the PDF has an embedded Table of Contents (bookmarks)
        toc = doc.get_toc()
        if toc and len(toc) >= 3:
            for idx, item in enumerate(toc):
                lvl, title, pno = item
                clean_title = " ".join(title.strip().split())
                if 1 <= pno <= total_pages and clean_title:
                    sections.append(
                        DocumentSection(
                            id=f"sec_{idx + 1}",
                            title=clean_title,
                            section_type=f"level_{lvl}",
                            start_page=pno,
                            end_page=pno,
                        )
                    )

        # 2. If no embedded TOC, detect explicit chapter and section headings in text
        if not sections:
            patterns = [
                # Upper/Title case CHAPTER with number and optional title
                (re.compile(r'(?:^|\n)\s*(CHAPTER\s*[-–:]?\s*(?:\d+|[IVXLCDM]+)[\s:.\-–]+[^\n\r]+)'), "chapter"),
                # Explicit "Section X.X: Title"
                (re.compile(r'(?:^|\n)\s*(Section\s*\d+(?:\.\d+)*[\s:.\-–]+[^\n\r]+)', re.IGNORECASE), "section"),
                # Numbered headings like "15.4. ATTENDANCE AND LEAVE OF ABSENCE"
                (re.compile(r'(?:^|\n)\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?\.?\s+[A-Z][A-Za-z0-9 ,/&\(\)\-–\':]{4,70})'), "section"),
            ]

            raw_headings = []
            seen_titles = set()

            for pno in range(pdf_page_count):
                page_num = pno + 1
                page = doc.load_page(pno)
                txt = page.get_text("text")

                for pat, stype in patterns:
                    for match in pat.finditer(txt):
                        raw = " ".join(match.group(1).strip().split())
                        # Skip common false positives
                        if len(raw) < 5 or "...." in raw or raw.lower() in seen_titles:
                            continue
                        seen_titles.add(raw.lower())
                        raw_headings.append({
                            "title": raw,
                            "start_page": page_num,
                            "section_type": stype,
                        })

            raw_headings.sort(key=lambda x: x["start_page"])

            # Filter: If document has multiple major chapters after front-matter (e.g. handbook), prefer chapters
            chapters = [h for h in raw_headings if h["section_type"] == "chapter" and h["start_page"] > 18]
            if len(chapters) >= 2:
                selected_headings = chapters
            else:
                selected_headings = raw_headings[:50]

            for idx, h in enumerate(selected_headings):
                sections.append(
                    DocumentSection(
                        id=f"sec_{idx + 1}",
                        title=h["title"],
                        section_type=h["section_type"],
                        start_page=h["start_page"],
                        end_page=h["start_page"],
                    )
                )

        doc.close()
    except Exception as e:
        logger.warning(f"Error extracting structure from PDF '{pdf_path}': {e}")

    # Compute continuous ending page numbers for each section
    for i in range(len(sections)):
        if i < len(sections) - 1:
            next_start = sections[i + 1].start_page
            if next_start > sections[i].start_page:
                sections[i].end_page = next_start - 1
            else:
                sections[i].end_page = sections[i].start_page
        else:
            sections[i].end_page = total_pages

    has_structure = len(sections) > 0

    return DocumentStructureResponse(
        document_id=document_id,
        filename=filename,
        total_pages=total_pages,
        has_structure=has_structure,
        sections=sections,
    )


def get_or_create_document_structure(document_id: str) -> Optional[DocumentStructureResponse]:
    """
    Retrieve document structure from local cache, or detect it from the stored PDF
    and persist it to data/metadata/document_structures.json.
    """
    structures = load_all_structures()
    if document_id in structures:
        try:
            return DocumentStructureResponse(**structures[document_id])
        except Exception as e:
            logger.warning(f"Corrupted cached structure for {document_id}: {e}")

    doc = get_document(document_id)
    if not doc:
        return None

    # Check for raw PDF
    raw_pdf_path = UPLOAD_DIR / doc.stored_filename
    if not raw_pdf_path.exists():
        # Check by doc_id prefix
        matches = list(UPLOAD_DIR.glob(f"{document_id}_*.pdf"))
        if matches:
            raw_pdf_path = matches[0]

    if not raw_pdf_path.exists():
        # Fallback: check chunks for section headings if PDF is missing
        return DocumentStructureResponse(
            document_id=document_id,
            filename=doc.filename,
            total_pages=doc.pages,
            has_structure=False,
            sections=[],
        )

    structure = detect_structure_from_pdf(
        pdf_path=raw_pdf_path,
        total_pages=doc.pages,
        document_id=document_id,
        filename=doc.filename,
    )

    # Persist to disk
    structures[document_id] = structure.model_dump()
    save_all_structures(structures)
    return structure
