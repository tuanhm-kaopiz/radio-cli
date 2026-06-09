from __future__ import annotations

import json
import time
from typing import Any

from radio_cli.config import HISTORY_FILE, ensure_dirs

MAX_ENTRIES = 100


def _load() -> list[dict[str, Any]]:
    ensure_dirs()
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return list(data.get("entries", []))
    except (json.JSONDecodeError, OSError):
        return []


def _save(entries: list[dict[str, Any]]) -> None:
    ensure_dirs()
    HISTORY_FILE.write_text(
        json.dumps({"entries": entries[:MAX_ENTRIES]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add(
    *,
    title: str,
    url: str,
    source: str,
    station_id: str | None = None,
) -> None:
    entries = _load()
    entry = {
        "title": title,
        "url": url,
        "source": source,
        "station_id": station_id,
        "played_at": time.time(),
    }
    entries = [e for e in entries if e.get("url") != url]
    entries.insert(0, entry)
    _save(entries)


def list_entries() -> list[dict[str, Any]]:
    return _load()


def get_entry(index: int) -> dict[str, Any] | None:
    """index 1-based."""
    entries = _load()
    if index < 1 or index > len(entries):
        return None
    return entries[index - 1]


def remove(index: int) -> dict[str, Any] | None:
    """Remove and return one history entry by 1-based index."""
    entries = _load()
    if index < 1 or index > len(entries):
        return None
    removed = entries.pop(index - 1)
    _save(entries)
    return removed


def clear() -> int:
    entries = _load()
    count = len(entries)
    _save([])
    return count
