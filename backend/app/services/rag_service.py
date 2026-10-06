import logging
from typing import List, Optional

from app.config import RAG_TOP_K, SIMILARITY_THRESHOLD
from app.models.chat import ChatResponse, SourceCitation
from app.models.search import SearchResult
from app.services.embeddings import generate_query_embedding
from app.services.ollama_client import OllamaClient, get_ollama_client
from app.services.vector_store import FaissVectorStore, get_vector_store

logger = logging.getLogger(__name__)

NO_EVIDENCE_ANSWER = "I couldn't find sufficient evidence for this answer in the uploaded documents."

SYSTEM_PROMPT = (
    "You are a factual, concise assistant for LocalDoc AI.\n"
    "Your task is to answer the user's question strictly and exclusively based on the provided document context.\n\n"
    "Rules:\n"
    "1. Answer ONLY using facts directly mentioned in the document context.\n"
    "2. Do NOT extrapolate, speculate, or introduce outside knowledge.\n"
    f"3. If the context does not contain enough information to answer the question, clearly respond with:\n"
    f"\"{NO_EVIDENCE_ANSWER}\"\n"
    "4. Give a concise and useful answer.\n"
    "5. Do not expose internal reasoning or thinking."
)


class RAGService:
    """Retrieval-Augmented Generation service combining FAISS search with local Gemma."""

    def __init__(
        self,
        vector_store: Optional[FaissVectorStore] = None,
        ollama_client: Optional[OllamaClient] = None,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        top_k: int = RAG_TOP_K,
    ):
        self._vector_store = vector_store
        self._ollama_client = ollama_client
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k

    @property
    def vector_store(self) -> FaissVectorStore:
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    @property
    def ollama_client(self) -> OllamaClient:
        if self._ollama_client is None:
            self._ollama_client = get_ollama_client()
        return self._ollama_client

    def answer_question(self, question: str, top_k: Optional[int] = None) -> ChatResponse:
        """
        Execute the complete RAG pipeline:
        1. Embed user query using existing embedding service.
        2. Perform vector similarity search on existing FAISS index.
        3. Evaluate evidence sufficiency.
        4. Construct grounded prompt with retrieved chunks.
        5. Invoke local Gemma 4 E2B model via Ollama.
        6. Return generated answer with deterministic source citations.
        """
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("Question cannot be empty.")

        # 1. Check if any vectors exist in index
        if self.vector_store.index.ntotal == 0:
            return ChatResponse(answer=NO_EVIDENCE_ANSWER, sources=[])

        # 2. Query embedding via existing embedding service
        query_vector = generate_query_embedding(cleaned_question)

        # 3. Vector search via existing FAISS index with candidate pool
        k = top_k or self.top_k
        candidate_k = max(k * 8, 32)
        raw_results: List[SearchResult] = self.vector_store.search(query_vector, top_k=candidate_k)

        # 4. Check for sufficient evidence and de-duplicate redundant chunks
        if not raw_results:
            return ChatResponse(answer=NO_EVIDENCE_ANSWER, sources=[])

        # Filter chunks meeting the similarity threshold and de-duplicate redundant content
        relevant_chunks: List[SearchResult] = []
        seen_texts = set()

        for r in raw_results:
            if r.score < self.similarity_threshold:
                continue
            normalized_text = " ".join(r.text.split())
            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)
            relevant_chunks.append(r)
            if len(relevant_chunks) >= k:
                break

        if not relevant_chunks:
            return ChatResponse(answer=NO_EVIDENCE_ANSWER, sources=[])

        # 5. Build grounded context blocks
        context_blocks = []
        for chunk in relevant_chunks:
            context_blocks.append(
                f"[{chunk.source}, page {chunk.page}]:\n\"{chunk.text}\""
            )
        context_text = "\n\n".join(context_blocks)

        user_prompt = (
            f"Context from uploaded documents:\n\n{context_text}\n\n"
            f"Question:\n{cleaned_question}\n\n"
            "Answer:"
        )

        # 6. Generate answer via local Gemma
        raw_answer = self.ollama_client.generate(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
        ).strip()

        # 7. Check if the model itself responded with insufficient evidence
        lower_ans = raw_answer.lower()
        if "couldn't find sufficient evidence" in lower_ans or "not found in the uploaded documents" in lower_ans:
            return ChatResponse(answer=NO_EVIDENCE_ANSWER, sources=[])

        # 8. Deterministic source citations from retrieved metadata
        seen_citations = set()
        sources: List[SourceCitation] = []

        for chunk in relevant_chunks:
            citation_key = (chunk.source, chunk.page)
            if citation_key not in seen_citations:
                seen_citations.add(citation_key)
                sources.append(
                    SourceCitation(
                        document=chunk.source,
                        page=chunk.page,
                    )
                )

        return ChatResponse(
            answer=raw_answer,
            sources=sources,
        )


# Singleton instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or initialize singleton RAGService."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
