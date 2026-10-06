from typing import List
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    """Source attribution for a grounded answer."""
    document: str = Field(..., description="Source document filename")
    page: int = Field(..., description="Page number where evidence is found")


class ChatRequest(BaseModel):
    """Chat question request payload."""
    question: str = Field(..., min_length=1, description="User question about uploaded documents")


class ChatResponse(BaseModel):
    """Chat response with grounded answer and deterministic sources."""
    answer: str = Field(..., description="Grounded answer synthesized from context")
    sources: List[SourceCitation] = Field(default_factory=list, description="List of source citations")
