import json
from pathlib import Path
from collections import defaultdict
import hashlib

proc_dir = Path(r"d:\hacktoberfest\data\processed")
files = list(proc_dir.glob("*.json"))

groups = defaultdict(list)
for f in files:
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    chunks = data.get("chunks", [])
    norm_text = " ".join(c.get("text", "").strip() for c in chunks)
    pages = data.get("pages", 0)
    filename = data.get("filename", "")
    fp_hash = hashlib.sha256(f"{pages}_{filename}_{norm_text}".encode("utf-8")).hexdigest()
    groups[fp_hash].append((f, data))

print(f"Total files: {len(files)}")
print(f"Total unique groups: {len(groups)}")

for fp_hash, doc_list in groups.items():
    primary = doc_list[0][1]
    print(f"\nGroup {fp_hash[:10]}: {primary['filename']} (pages={primary['pages']}) - {len(doc_list)} copies")
    for p, d in doc_list:
        print(f"   {d['document_id']} | status={d.get('indexing_status')} | file={p.name}")
