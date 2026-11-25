#!/usr/bin/env python3
"""Hash every final return file except the manifest itself."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RETURN = ROOT / "hardware/evt1-native-eda-20261118/kimi-h02-return"
output = RETURN / "delivery-manifest.json"
files = []
for path in sorted(item for item in RETURN.rglob("*") if item.is_file() and item != output):
    data = path.read_bytes()
    files.append({"path": path.relative_to(RETURN).as_posix(), "bytes": len(data),
                  "sha256": hashlib.sha256(data).hexdigest()})
manifest = {"schema": "H02_DELIVERY_FILE_MANIFEST_V1", "fileCount": len(files),
            "totalBytes": sum(item["bytes"] for item in files), "files": files}
output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"fileCount": len(files), "totalBytes": manifest["totalBytes"], "manifest": str(output)}))
