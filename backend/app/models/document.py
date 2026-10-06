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
    display_title: Optional[str] = Field(None, description="Clean human-readable title")
    stored_filename: str = Field(..., description="Safe filename stored on disk")
    pages: int = Field(..., description="Total number of pages processed")
    chunks: int = Field(..., description="Total number of text chunks generated")
    status: str = Field(..., description="Processing status (e.g. processed, already_exists)")
    indexing_status: str = Field(default="indexed", description="Vector indexing status")
    message: Optional[str] = Field(None, description="Informational status message")


class DocumentMetadata(BaseModel):
    """Full metadata and chunks of a processed document stored locally."""
    document_id: str
    filename: str
    display_title: Optional[str] = None
    stored_filename: str
    file_size_bytes: int
    pages: int
    chunks_count: int
    created_at: str
    status: str
    indexing_status: str = Field(default="indexed", description="Vector index status: indexed, pending, or failed")
    content_hash: Optional[str] = None
    duplicate_count: int = 1
    chunks: List[Chunk] = Field(default_factory=list)


class DocumentSection(BaseModel):
    """A detected section or chapter within a document."""
    id: str = Field(..., description="Unique section identifier (e.g. sec_1)")
    title: str = Field(..., description="Section or chapter title")
    section_type: str = Field(default="section", description="Section type: chapter, section, etc.")
    start_page: int = Field(..., description="1-based starting page number")
    end_page: int = Field(..., description="1-based ending page number")


class DocumentStructureResponse(BaseModel):
    """Document organization structure containing detected sections and page ranges."""
    document_id: str = Field(..., description="Document identifier")
    filename: str = Field(..., description="Original filename")
    total_pages: int = Field(..., description="Total pages in document")
    has_structure: bool = Field(..., description="Whether sections were detected")
    sections: List[DocumentSection] = Field(default_factory=list, description="Ordered list of sections")


class KnowledgeTopic(BaseModel):
    """A specific topic identified within a knowledge category."""
    name: str = Field(..., description="Topic name")
    source_section: Optional[str] = Field(None, description="Source section or chapter heading")
    start_page: int = Field(..., description="Starting page")
    end_page: int = Field(..., description="Ending page")


class KnowledgeCategory(BaseModel):
    """A high-level category supported by actual document content."""
    category_id: str = Field(..., description="Unique category slug (e.g. academic, attendance)")
    name: str = Field(..., description="Display name of category")
    icon: str = Field(default="📄", description="Emoji icon for category")
    topics: List[KnowledgeTopic] = Field(default_factory=list, description="Topics within this category")


class KeyInformation(BaseModel):
    """An extracted factual statement grounded in document content."""
    title: str = Field(..., description="Fact or policy title")
    value: str = Field(..., description="Extracted factual value")
    source_page: int = Field(..., description="Source page number")
    source_section: Optional[str] = Field(None, description="Source section name")
    source_document: Optional[str] = Field(None, description="Source document filename")


class SuggestedQuestion(BaseModel):
    """A natural question generated from real document topics."""
    category: str = Field(..., description="Category name (e.g. Attendance)")
    question: str = Field(..., description="Suggested question text")


class DocumentKnowledgeResponse(BaseModel):
    """Complete document knowledge model containing overview, categories, key facts, and questions."""
    document_id: str = Field(..., description="Document identifier")
    filename: str = Field(..., description="Source document filename")
    total_pages: int = Field(..., description="Total pages")
    overview: str = Field(..., description="Grounded document overview")
    categories: List[KnowledgeCategory] = Field(default_factory=list, description="Grounded knowledge categories")
    key_information: List[KeyInformation] = Field(default_factory=list, description="Extracted factual highlights")
    suggested_questions: List[SuggestedQuestion] = Field(default_factory=list, description="Suggested questions for chat")

