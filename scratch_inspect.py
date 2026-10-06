import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(r"d:\hacktoberfest\backend")))

from app.services.storage import list_documents, PROCESSED_DATA_DIR, UPLOAD_DIR
from app.models.document import DocumentMetadata
import json

files = list(PROCESSED_DATA_DIR.glob("*.json"))
print(f"Total processed files on disk: {len(files)}")

unique_docs = list_documents()
print(f"list_documents returned: {len(unique_docs)} documents")

for doc in unique_docs:
    print(f"- {doc.document_id} | {doc.display_title} ({doc.filename}) | {doc.pages} pages | {len(doc.chunks)} chunks | status={doc.indexing_status} | dup_count={doc.duplicate_count}")
