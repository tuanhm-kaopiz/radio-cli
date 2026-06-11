from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from radio_cli.config import AUDIO_HUB_FILE, FAVORITES_FILE, HISTORY_FILE, PLAYLISTS_FILE, QUEUE_FILE, ensure_dirs

DATA_FILES = {
    "favorites": FAVORITES_FILE,
    "history": HISTORY_FILE,
    "queue": QUEUE_FILE,
    "audio_hub": AUDIO_HUB_FILE,
"playlists": PLAYLISTS_FILE,
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Không đọc được {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} không phải JSON object.")
    return data


def export_data(path: Path) -> Path:
    ensure_dirs()
    payload = {
        "version": 1,
        "exported_at": time.time(),
        "data": {name: _read_json(file_path) for name, file_path in DATA_FILES.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def import_data(path: Path, *, merge: bool = False) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Không đọc được file import: {exc}") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ValueError("File import không đúng định dạng radio-cli.")

    ensure_dirs()
    imported: list[str] = []
    for name, file_path in DATA_FILES.items():
        incoming = data.get(name)
        if incoming is None:
            continue
        if not isinstance(incoming, dict):
            raise ValueError(f"Nhóm dữ liệu {name} không phải JSON object.")
        if merge and file_path.exists():
            current = _read_json(file_path)
            current.update(incoming)
            incoming = current
        file_path.write_text(json.dumps(incoming, ensure_ascii=False, indent=2), encoding="utf-8")
        imported.append(name)
    return imported
