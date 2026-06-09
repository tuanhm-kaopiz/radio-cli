from __future__ import annotations

import json
from typing import Any

from radio_cli.config import FAVORITES_FILE, ensure_dirs
from radio_cli.stations import station_by_id


def _load_raw() -> dict[str, Any]:
    ensure_dirs()
    if not FAVORITES_FILE.exists():
        return {"stations": [], "tracks": []}
    try:
        return json.loads(FAVORITES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"stations": [], "tracks": []}


def _save_raw(data: dict[str, Any]) -> None:
    ensure_dirs()
    FAVORITES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_station_ids() -> list[str]:
    return list(_load_raw().get("stations", []))


def list_tracks() -> list[dict[str, str]]:
    return list(_load_raw().get("tracks", []))


def add_station(station_id: str) -> bool:
    if station_by_id(station_id) is None:
        return False
    data = _load_raw()
    stations: list[str] = data.setdefault("stations", [])
    if station_id not in stations:
        stations.append(station_id)
        _save_raw(data)
    return True


def remove_station(station_id: str) -> bool:
    data = _load_raw()
    stations: list[str] = data.setdefault("stations", [])
    if station_id not in stations:
        return False
    stations.remove(station_id)
    _save_raw(data)
    return True


def add_track(title: str, url: str, video_id: str = "") -> None:
    data = _load_raw()
    tracks: list[dict[str, str]] = data.setdefault("tracks", [])
    entry = {"title": title, "url": url, "video_id": video_id}
    tracks = [t for t in tracks if t.get("url") != url]
    tracks.insert(0, entry)
    data["tracks"] = tracks[:50]
    _save_raw(data)


def get_track(index: int) -> dict[str, str] | None:
    """index 1-based."""
    tracks = list_tracks()
    if index < 1 or index > len(tracks):
        return None
    return tracks[index - 1]


def remove_track(url: str) -> bool:
    data = _load_raw()
    tracks: list[dict[str, str]] = data.setdefault("tracks", [])
    before = len(tracks)
    data["tracks"] = [t for t in tracks if t.get("url") != url]
    if len(data["tracks"]) == before:
        return False
    _save_raw(data)
    return True
