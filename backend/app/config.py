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
