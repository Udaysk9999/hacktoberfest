from pathlib import Path
from typing import List, Union
import pymupdf as fitz

from app.models.document import PageExtraction
from app.services.text_cleaner import clean_text


class PDFProcessingError(Exception):
    """Base exception for PDF processing errors."""
    pass


class PasswordProtectedPDFError(PDFProcessingError):
    """Raised when PDF is encrypted and requires a password."""
    pass


class EmptyPDFError(PDFProcessingError):
    """Raised when PDF has zero pages or zero content."""
    pass


class ScannedPDFError(PDFProcessingError):
    """Raised when PDF contains only scanned images and no extractable text."""
    pass


class CorruptedPDFError(PDFProcessingError):
    """Raised when PDF file is invalid or corrupted."""
    pass


def extract_text_from_pdf(
    file_path: Union[str, Path],
    source_filename: str,
) -> List[PageExtraction]:
    """
    Extract text page-by-page from a PDF file using PyMuPDF.
    
    - Preserves 1-based page numbers.
    - Applies text cleaning to each page.
    - Handles empty/unextractable pages gracefully without crashing.
    - Raises specific exceptions for encrypted, empty, corrupted, or scanned PDFs.
    """
    path = Path(file_path)
    if not path.exists():
        raise CorruptedPDFError(f"PDF file does not exist at {path}")

    if path.stat().st_size == 0:
        raise EmptyPDFError("The uploaded PDF file is empty (0 bytes).")

    try:
        doc = fitz.open(str(path))
    except (fitz.FileDataError, fitz.EmptyFileError) as e:
        raise CorruptedPDFError(f"Failed to parse PDF: The file appears corrupted or invalid ({str(e)}).")
    except Exception as e:
        raise CorruptedPDFError(f"Failed to open PDF document: {str(e)}")

    try:
        # Check for encryption / password protection
        if doc.is_encrypted:
            raise PasswordProtectedPDFError(
                "PDF is password-protected. Please provide an unencrypted document."
            )

        total_pages = doc.page_count
        if total_pages == 0:
            raise EmptyPDFError("The uploaded PDF has 0 pages.")

        extracted_pages: List[PageExtraction] = []
        has_any_usable_text = False

        for page_index in range(total_pages):
            page_num = page_index + 1
            try:
                page = doc.load_page(page_index)
                # Extract text blocks (block_type 0 is text) to preserve structural paragraphs
                blocks = page.get_text("blocks") or []
                text_blocks = [b[4] for b in blocks if len(b) > 4 and b[6] == 0]
                if text_blocks:
                    raw_text = "\n\n".join(text_blocks)
                else:
                    raw_text = page.get_text("text") or ""
                cleaned = clean_text(raw_text)
                has_text = bool(cleaned.strip())

                if has_text:
                    has_any_usable_text = True

                extracted_pages.append(
                    PageExtraction(
                        page=page_num,
                        text=cleaned,
                        source=source_filename,
                        has_text=has_text,
                    )
                )
            except Exception as page_err:
                # If a single page fails to extract, do not crash; record as empty/unextractable
                extracted_pages.append(
                    PageExtraction(
                        page=page_num,
                        text="",
                        source=source_filename,
                        has_text=False,
                    )
                )

        # Check if entire PDF is scanned or image-only
        if not has_any_usable_text:
            raise ScannedPDFError(
                "The uploaded PDF contains no extractable text. Scanned or image-only "
                "PDFs requiring OCR are not currently supported."
            )

        return extracted_pages

    finally:
        doc.close()
