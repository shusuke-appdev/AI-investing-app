"""Thread-safe atomic JSON file helpers for local persistence."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

_locks_guard = threading.Lock()
_locks: dict[Path, threading.RLock] = {}


def _path_lock(path: Path) -> threading.RLock:
    resolved = path.resolve()
    with _locks_guard:
        return _locks.setdefault(resolved, threading.RLock())


def read_json(path: Path, default: Any) -> Any:
    """Read JSON while coordinating with in-process writers."""

    with _path_lock(path):
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any, *, indent: int = 2) -> None:
    """Atomically replace a JSON file after flushing it to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with _path_lock(path):
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(value, file, ensure_ascii=False, indent=indent)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()


def update_json(path: Path, default: Any, update: Callable[[Any], Any]) -> Any:
    """Apply a read-modify-write transaction under the file's process lock."""

    with _path_lock(path):
        current = read_json(path, default)
        updated = update(current)
        write_json(path, updated)
        return updated


def delete_file(path: Path) -> bool:
    """Delete a local data file under the same lock used by readers/writers."""

    with _path_lock(path):
        if not path.exists():
            return False
        path.unlink()
        return True
