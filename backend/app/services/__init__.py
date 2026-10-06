"""LocalDoc AI application services."""
from app.services.chunker import chunk_document_pages, chunk_page_text
from app.services.pdf_processor import (
    CorruptedPDFError,
    EmptyPDFError,
    PasswordProtectedPDFError,
    PDFProcessingError,
    ScannedPDFError,
    extract_text_from_pdf,
)
from app.services.embeddings import (
    generate_embeddings,
    generate_query_embedding,
    get_embedding_model,
)
from app.services.ollama_client import (
    OllamaClient,
    OllamaClientError,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    get_ollama_client,
)
from app.services.rag_service import (
    NO_EVIDENCE_ANSWER,
    RAGService,
    get_rag_service,
)
from app.services.storage import (
    get_chunks,
    get_document,
    list_documents,
    save_document,
    save_uploaded_pdf,
)
from app.services.text_cleaner import clean_text
from app.services.vector_store import (
    FaissVectorStore,
    get_vector_store,
)

__all__ = [
    "clean_text",
    "extract_text_from_pdf",
    "chunk_document_pages",
    "chunk_page_text",
    "save_uploaded_pdf",
    "save_document",
    "get_document",
    "get_chunks",
    "list_documents",
    "generate_embeddings",
    "generate_query_embedding",
    "get_embedding_model",
    "FaissVectorStore",
    "get_vector_store",
    "OllamaClient",
    "get_ollama_client",
    "OllamaClientError",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "OllamaModelNotFoundError",
    "RAGService",
    "get_rag_service",
    "NO_EVIDENCE_ANSWER",
    "PDFProcessingError",
    "PasswordProtectedPDFError",
    "EmptyPDFError",
    "ScannedPDFError",
    "CorruptedPDFError",
]
