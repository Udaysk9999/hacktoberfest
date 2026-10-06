import json
from pathlib import Path
from collections import defaultdict
import hashlib

proc_dir = Path(r"d:\hacktoberfest\data\processed")
files = list(proc_dir.glob("*.json"))

docs = []
for f in files:
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    docs.append(data)

print(f"Total docs: {len(docs)}")

# Group by filename
by_filename = defaultdict(list)
for d in docs:
    by_filename[d["filename"]].append(d)

for fname, dlist in by_filename.items():
    print(f"\nFilename: {fname} (Total copies: {len(dlist)})")
    # Group by extracted text
    text_groups = defaultdict(list)
    for d in dlist:
        chunks = d.get("chunks", [])
        norm_text = " ".join(c.get("text", "").strip() for c in chunks)
        text_hash = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()[:12]
        pages = d.get("pages", 0)
        key = (pages, text_hash)
        text_groups[key].append(d["document_id"])
    for key, doc_ids in text_groups.items():
        print(f"  Pages={key[0]}, TextHash={key[1]}: {len(doc_ids)} records -> {doc_ids[:3]}...")
