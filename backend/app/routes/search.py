from fastapi import APIRouter, HTTPException, status

from app.config import DEFAULT_TOP_K
from app.models.search import SearchRequest, SearchResponse
from app.services.embeddings import generate_query_embedding
from app.services.vector_store import get_vector_store

router = APIRouter(tags=["search"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic vector search across indexed documents",
)
def semantic_search(request: SearchRequest):
    """
    Search indexed document chunks using cosine similarity over local embeddings.
    Returns ranked results with full chunk text, source filename, page, and similarity score.
    """
    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty.",
        )

    vector_store = get_vector_store()
    if vector_store.index.ntotal == 0:
        return SearchResponse(query=query_text, results=[])

    # 1. Generate normalized query embedding
    try:
        query_vector = generate_query_embedding(query_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}",
        )

    # 2. Query FAISS vector index
    top_k = request.top_k or DEFAULT_TOP_K
    fetch_k = top_k * 4 if request.document_id else top_k
    results = vector_store.search(query_embedding=query_vector, top_k=fetch_k)

    if request.document_id:
        results = [r for r in results if r.document_id == request.document_id][:top_k]

    return SearchResponse(
        query=query_text,
        results=results,
    )
