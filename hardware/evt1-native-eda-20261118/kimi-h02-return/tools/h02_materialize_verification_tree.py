#!/usr/bin/env python3
"""Materialize verifier filenames from immutable raw command responses."""
import argparse
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    manifest = json.loads((root / "board_pages.json").read_text(encoding="utf-8"))
    pages = [page for board in manifest["boards"].values() for page in board]
    (root / "sch").mkdir(exist_ok=True)
    for page in pages:
        shutil.copyfile(root / "connectivity" / f"{page}.stdout.json", root / "sch" / f"{page}.json")
        shutil.copyfile(root / "pins" / f"{page}.stdout.json", root / "pins" / f"{page}.json")
    for name in ("lceda-boards", "lceda-pages"):
        shutil.copyfile(root / f"{name}.stdout.json", root / f"{name}.json")
    print(json.dumps({"status": "PASS", "pages": len(pages), "directory": str(root)}))


if __name__ == "__main__":
    main()
