import threading
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_DIM, EMBEDDING_MODEL_NAME

_model_lock = threading.Lock()
_embedding_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """
    Get or lazily initialize the SentenceTransformer embedding model.
    Thread-safe singleton pattern.
    """
    global _embedding_model
    if _embedding_model is None:
        with _model_lock:
            if _embedding_model is None:
                # Load locally; will use local cache once downloaded
                _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def generate_embeddings(texts: List[str]) -> np.ndarray:
    """
    Generate normalized float32 embeddings for a list of texts.
    Returns 2D numpy array of shape (len(texts), EMBEDDING_DIM).
    """
    if not texts:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype=np.float32)


def generate_query_embedding(query: str) -> np.ndarray:
    """
    Generate a normalized float32 embedding vector for a single query string.
    Returns 1D numpy array of shape (EMBEDDING_DIM,).
    """
    model = get_embedding_model()
    embedding = model.encode(
        query,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embedding, dtype=np.float32)
