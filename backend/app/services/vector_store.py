import json
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Set

import faiss
import numpy as np

from app.config import (
    DEFAULT_TOP_K,
    EMBEDDING_DIM,
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
)
from app.models.document import Chunk
from app.models.search import SearchResult

logger = logging.getLogger(__name__)


class FaissVectorStore:
    """
    Local FAISS Vector Store implementing cosine similarity via normalized inner product.
    Persists vectors to FAISS binary format and chunk metadata to a JSON mapping.
    """

    def __init__(
        self,
        dimension: int = EMBEDDING_DIM,
        index_path: Path = FAISS_INDEX_PATH,
        metadata_path: Path = FAISS_METADATA_PATH,
    ):
        self.dimension = dimension
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.lock = threading.Lock()

        # In-memory index and metadata structures
        self.index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.dimension)
        # Vector ID (as int) -> chunk metadata dictionary
        self.id_to_metadata: Dict[int, Dict[str, Any]] = {}
        # Set of chunk IDs already present in this index
        self.indexed_chunk_ids: Set[str] = set()
        # Set of document IDs already indexed
        self.indexed_doc_ids: Set[str] = set()

        # Load existing index if present on disk
        self.load()

    def load(self) -> bool:
        """Load FAISS index and metadata store from disk if they exist."""
        with self.lock:
            if not self.index_path.exists() or not self.metadata_path.exists():
                logger.info("No existing FAISS index found. Starting with a fresh index.")
                return False

            try:
                # 1. Load FAISS index
                loaded_index = faiss.read_index(str(self.index_path))
                self.index = loaded_index

                # 2. Load metadata JSON
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                raw_meta = data.get("metadata", {})
                self.id_to_metadata = {int(k): v for k, v in raw_meta.items()}
                self.indexed_doc_ids = set(data.get("indexed_documents", []))
                self.indexed_chunk_ids = {
                    item["chunk_id"] for item in self.id_to_metadata.values() if "chunk_id" in item
                }
                logger.info(
                    f"Successfully loaded FAISS index with {self.index.ntotal} vectors "
                    f"and {len(self.indexed_doc_ids)} documents."
                )
                return True
            except Exception as e:
                logger.error(f"Failed to load existing FAISS index: {e}. Initializing fresh index.")
                self.index = faiss.IndexFlatIP(self.dimension)
                self.id_to_metadata = {}
                self.indexed_chunk_ids = set()
                self.indexed_doc_ids = set()
                return False

    def save(self) -> None:
        """Persist FAISS index binary and metadata JSON to disk."""
        # Ensure directories exist
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Save FAISS index
        faiss.write_index(self.index, str(self.index_path))

        # 2. Save metadata mapping
        meta_payload = {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "indexed_documents": sorted(list(self.indexed_doc_ids)),
            "metadata": {str(k): v for k, v in self.id_to_metadata.items()},
        }
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f, indent=2, ensure_ascii=False)

    def is_document_indexed(self, document_id: str) -> bool:
        """Check if a document has already been indexed."""
        with self.lock:
            return document_id in self.indexed_doc_ids

    def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: np.ndarray,
        document_id: str,
        reindex: bool = False,
    ) -> int:
        """
        Add chunks and their normalized embedding vectors into the FAISS index.
        Thread-safe and persists to disk immediately.
        Returns the number of new chunks indexed.
        """
        if not chunks:
            return 0

        with self.lock:
            # Check if document already indexed and reindex is not requested
            if document_id in self.indexed_doc_ids and not reindex:
                logger.info(f"Document '{document_id}' already indexed. Skipping.")
                return 0

            # Filter out chunks that are already in the index if reindex is False
            valid_chunks: List[Chunk] = []
            valid_indices: List[int] = []

            for i, chunk in enumerate(chunks):
                if reindex or (chunk.chunk_id not in self.indexed_chunk_ids):
                    valid_chunks.append(chunk)
                    valid_indices.append(i)

            if not valid_chunks:
                self.indexed_doc_ids.add(document_id)
                return 0

            # Filter embeddings to match valid chunks
            valid_embeddings = embeddings[valid_indices]
            if valid_embeddings.dtype != np.float32:
                valid_embeddings = valid_embeddings.astype(np.float32)

            # Ensure 2D shape (N, dim)
            if len(valid_embeddings.shape) == 1:
                valid_embeddings = np.expand_dims(valid_embeddings, axis=0)

            # Assign sequential IDs based on current total
            start_id = self.index.ntotal
            self.index.add(valid_embeddings)

            # Update metadata
            for i, chunk in enumerate(valid_chunks):
                vec_id = start_id + i
                self.id_to_metadata[vec_id] = {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "source": chunk.source,
                    "page": chunk.page,
                    "text": chunk.text,
                }
                self.indexed_chunk_ids.add(chunk.chunk_id)

            self.indexed_doc_ids.add(document_id)
            self.save()
            return len(valid_chunks)

    def search(self, query_embedding: np.ndarray, top_k: int = DEFAULT_TOP_K) -> List[SearchResult]:
        """
        Perform vector similarity search against the FAISS index.
        Returns ranked SearchResult objects with original chunk metadata and similarity scores.
        """
        with self.lock:
            if self.index.ntotal == 0:
                return []

            # Prepare query vector
            q_vec = np.asarray(query_embedding, dtype=np.float32)
            if len(q_vec.shape) == 1:
                q_vec = np.expand_dims(q_vec, axis=0)

            k = min(top_k, self.index.ntotal)
            distances, indices = self.index.search(q_vec, k)

            results: List[SearchResult] = []
            row_indices = indices[0]
            row_scores = distances[0]

            for idx, score in zip(row_indices, row_scores):
                if idx == -1 or idx not in self.id_to_metadata:
                    continue

                meta = self.id_to_metadata[idx]
                # Cosine similarity on normalized vectors is between -1.0 and 1.0 (typically 0.0 to 1.0 for text)
                clean_score = round(float(score), 4)

                results.append(
                    SearchResult(
                        chunk_id=meta["chunk_id"],
                        document_id=meta["document_id"],
                        text=meta["text"],
                        source=meta["source"],
                        page=meta["page"],
                        score=clean_score,
                    )
                )

            # Sort by score descending
            results.sort(key=lambda x: x.score, reverse=True)
            return results

    def clear(self) -> None:
        """Reset index and metadata completely (useful for tests)."""
        with self.lock:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.id_to_metadata = {}
            self.indexed_chunk_ids = set()
            self.indexed_doc_ids = set()
            if self.index_path.exists():
                self.index_path.unlink()
            if self.metadata_path.exists():
                self.metadata_path.unlink()


# Global vector store singleton
_vector_store_instance: Optional[FaissVectorStore] = None
_vs_lock = threading.Lock()


def get_vector_store() -> FaissVectorStore:
    """Get or initialize the global FaissVectorStore instance."""
    global _vector_store_instance
    if _vector_store_instance is None:
        with _vs_lock:
            if _vector_store_instance is None:
                _vector_store_instance = FaissVectorStore()
    return _vector_store_instance
