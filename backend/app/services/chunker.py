from typing import List
from app.config import CHUNK_SIZE, CHUNK_OVERLAP
from app.models.document import Chunk, PageExtraction


def find_split_point(text: str, target: int, min_point: int) -> int:
    """
    Find a natural break point in `text` near `target`, not before `min_point`.
    Checks in priority order:
    1. Paragraph break (\n\n)
    2. Line break (\n)
    3. Sentence end (. , ! , ? )
    4. Word space ( )
    """
    search_window = text[min_point:target]
    if not search_window:
        return target

    # 1. Paragraph boundary
    idx = search_window.rfind("\n\n")
    if idx != -1:
        return min_point + idx + 2

    # 2. Line boundary
    idx = search_window.rfind("\n")
    if idx != -1:
        return min_point + idx + 1

    # 3. Sentence boundary
    for punct in [". ", "? ", "! "]:
        idx = search_window.rfind(punct)
        if idx != -1:
            return min_point + idx + len(punct)

    # 4. Word boundary
    idx = search_window.rfind(" ")
    if idx != -1:
        return min_point + idx + 1

    return target


def chunk_page_text(
    text: str,
    document_id: str,
    source: str,
    page: int,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[Chunk]:
    """
    Split text of a single page into overlapping chunks.
    Preserves page number, document ID, and source filename.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 4)

    total_len = len(cleaned)
    if total_len <= chunk_size:
        return [
            Chunk(
                chunk_id=f"{document_id}_page{page}_chunk1",
                document_id=document_id,
                source=source,
                page=page,
                text=cleaned,
            )
        ]

    chunks: List[Chunk] = []
    start = 0
    chunk_idx = 1

    while start < total_len:
        target_end = start + chunk_size
        if target_end >= total_len:
            chunk_slice = cleaned[start:].strip()
            if chunk_slice:
                chunks.append(
                    Chunk(
                        chunk_id=f"{document_id}_page{page}_chunk{chunk_idx}",
                        document_id=document_id,
                        source=source,
                        page=page,
                        text=chunk_slice,
                    )
                )
            break

        # Search for a natural boundary in the second half of the chunk window
        min_point = start + max(1, chunk_size - chunk_overlap)
        split_at = find_split_point(cleaned, target_end, min_point)

        chunk_slice = cleaned[start:split_at].strip()
        if chunk_slice:
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}_page{page}_chunk{chunk_idx}",
                    document_id=document_id,
                    source=source,
                    page=page,
                    text=chunk_slice,
                )
            )
            chunk_idx += 1

        # Advance start with overlap
        next_start = split_at - chunk_overlap
        if next_start <= start:
            next_start = split_at  # Guarantee forward progress

        # Skip leading whitespace for next chunk
        while next_start < total_len and cleaned[next_start].isspace():
            next_start += 1

        start = next_start

    return chunks


def chunk_document_pages(
    pages: List[PageExtraction],
    document_id: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[Chunk]:
    """
    Chunk all extracted pages of a document while preserving page-level metadata.
    """
    all_chunks: List[Chunk] = []
    for page_data in pages:
        if not page_data.has_text or not page_data.text:
            continue
        page_chunks = chunk_page_text(
            text=page_data.text,
            document_id=document_id,
            source=page_data.source,
            page=page_data.page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        all_chunks.extend(page_chunks)

    return all_chunks
