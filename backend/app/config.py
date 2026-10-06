import os
from pathlib import Path

# Resolve base and project directories
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Storage paths
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "uploads")))
PROCESSED_DATA_DIR = Path(os.getenv("PROCESSED_DATA_DIR", str(PROJECT_ROOT / "data" / "processed")))

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Upload constraints
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/acrobat",
    "applications/vnd.pdf",
    "text/pdf",
    "application/octet-stream",  # Fallback often sent by some clients/browsers; checked alongside magic bytes
}

# Chunking configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

# Vector Store & Embedding configuration
FAISS_DIR = Path(os.getenv("FAISS_DIR", str(PROJECT_ROOT / "data" / "faiss")))
METADATA_DIR = Path(os.getenv("METADATA_DIR", str(PROJECT_ROOT / "data" / "metadata")))

# Ensure vector store directories exist
FAISS_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)

FAISS_INDEX_PATH = FAISS_DIR / "index.faiss"
FAISS_METADATA_PATH = METADATA_DIR / "chunks_metadata.json"

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # Standard dimension for all-MiniLM-L6-v2
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))

# Ollama & Local RAG configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b-it-q4_K_M")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.25"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
