
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List, Dict

SUPPORTED_EXTENSIONS = {".txt", ".csv", ".pdf", ".docx"}


def compute_file_hash(file_path: str, block_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_folder(folder_path: str, recursive: bool = True) -> List[Dict]:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise ValueError("Folder path does not exist or is not a valid directory.")

    iterator = folder.rglob("*") if recursive else folder.glob("*")
    discovered = []

    for path in iterator:
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        stat = path.stat()
        discovered.append(
            {
                "file_path": str(path.resolve()),
                "file_name": path.name,
                "extension": ext.lstrip(".").upper(),
                "file_size": int(stat.st_size),
                "modified_time": float(stat.st_mtime),
            }
        )
    return discovered
