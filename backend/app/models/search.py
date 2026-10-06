from typing import List, Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """User semantic search query."""
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of top matching chunks to return")
    document_id: Optional[str] = Field(None, description="Optional document ID to restrict search to a single document")


class SearchResult(BaseModel):
    """A single retrieved chunk with its similarity score and source metadata."""
    chunk_id: str = Field(..., description="Unique chunk ID (e.g. doc1_page12_chunk2)")
    document_id: str = Field(..., description="Parent document identifier")
    text: str = Field(..., description="Text content of the retrieved chunk")
    source: str = Field(..., description="Original filename of the source document")
    page: int = Field(..., description="1-based page number where the chunk originates")
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")


class SearchResponse(BaseModel):
    """Search endpoint response with ranked results."""
    query: str = Field(..., description="Original search query")
    results: List[SearchResult] = Field(default_factory=list, description="Ranked matching chunks")


class IndexRequest(BaseModel):
    """Request to index processed document chunks."""
    document_id: Optional[str] = Field(None, description="Optional document ID to index. If omitted, indexes all unindexed documents.")
    reindex: bool = Field(False, description="Whether to re-index documents that have already been indexed.")


class IndexResponse(BaseModel):
    """Response returned after indexing documents into FAISS."""
    status: str
    indexed_documents: int
    indexed_chunks: int
    total_vectors_in_index: int
    embedding_model: str
