"""Result writer utilities for pipeline outputs."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


class ResultWriter:
    """Centralized filesystem writes for pipeline outputs.

    Thread safety: each document writes to its own subtree
    (``claims/{claim_id}/docs/{doc_id}/...``), so concurrent
    ``ResultWriter`` calls from different document threads never
    contend on the same file.  No additional locking is required
    when using ``ThreadPoolExecutor`` for parallel document processing.
    """

    def write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def write_json_atomic(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        tmp_path.replace(path)

    def write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def copy_file(self, src: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(src) and os.path.exists(dest) and os.path.samefile(src, dest):
            return  # Source and destination are the same file (e.g. --from-workspace)
        shutil.copy2(src, dest)

    def touch(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
