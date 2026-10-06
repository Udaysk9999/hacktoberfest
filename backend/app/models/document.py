from typing import List, Optional
from pydantic import BaseModel, Field


class PageExtraction(BaseModel):
    """Extracted text and metadata for a single page of a document."""
    page: int = Field(..., description="1-based page number")
    text: str = Field(..., description="Extracted clean text content of the page")
    source: str = Field(..., description="Original filename of the document")
    has_text: bool = Field(True, description="Whether this page contained usable text")


class Chunk(BaseModel):
    """A semantic text chunk with metadata for retrieval and embeddings."""
    chunk_id: str = Field(..., description="Unique identifier for the chunk (e.g. doc1_page12_chunk2)")
    document_id: str = Field(..., description="Unique identifier of the parent document")
    source: str = Field(..., description="Original filename of the document")
    page: int = Field(..., description="1-based page number from which chunk was extracted")
    text: str = Field(..., description="Clean chunk text content")


class DocumentUploadResponse(BaseModel):
    """API response model for document uploads."""
    document_id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original uploaded filename")
    stored_filename: str = Field(..., description="Safe filename stored on disk")
    pages: int = Field(..., description="Total number of pages processed")
    chunks: int = Field(..., description="Total number of text chunks generated")
    status: str = Field(..., description="Processing status (e.g. processed)")


class DocumentMetadata(BaseModel):
    """Full metadata and chunks of a processed document stored locally."""
    document_id: str
    filename: str
    stored_filename: str
    file_size_bytes: int
    pages: int
    chunks_count: int
    created_at: str
    status: str
    chunks: List[Chunk] = Field(default_factory=list)
