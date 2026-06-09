from __future__ import annotations

import json
import time
from typing import Any

from radio_cli.config import QUEUE_FILE, ensure_dirs
from radio_cli import audio_hub, stations
from radio_cli.url_utils import UrlValidationError, validate_http_url

MAX_ITEMS = 200


def _load() -> list[dict[str, Any]]:
    ensure_dirs()
    if not QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        return list(data.get("items", []))
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: list[dict[str, Any]]) -> None:
    ensure_dirs()
    QUEUE_FILE.write_text(
        json.dumps({"items": items[:MAX_ITEMS]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_item(
    *,
    title: str,
    url: str,
    source: str = "url",
    station_id: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "url": url,
        "source": source,
        "station_id": station_id,
        "added_at": time.time(),
    }


def item_from_station(station: dict[str, Any]) -> dict[str, Any]:
    return make_item(
        title=station["name"],
        url=station["url"],
        source="station",
        station_id=station["id"],
    )


def item_from_target(target: str) -> dict[str, Any] | None:
    if target.startswith(("http://", "https://")):
        try:
            url = validate_http_url(target, field_name="URL stream")
        except UrlValidationError:
            return None
        return make_item(title=url, url=url, source="url")
    if "://" in target:
        return None
    if target.startswith("hub:"):
        parts = target.split(":", 2)
        if len(parts) != 3:
            return None
        try:
            episode = audio_hub.get_episode(parts[1], int(parts[2]))
        except (ValueError, OSError, TimeoutError):
            return None
        if episode is None:
            return None
        return make_item(title=episode["title"], url=episode["url"], source=episode.get("source", "podcast"))
    station = stations.resolve_station(target, stations.load_stations())
    if station is None:
        return None
    return item_from_station(station)


def has_url(url: str) -> bool:
    return any(item.get("url") == url for item in _load())


def add_item(item: dict[str, Any], *, allow_duplicate: bool = False) -> int:
    items = _load()
    if not allow_duplicate and any(existing.get("url") == item.get("url") for existing in items):
        return len(items)
    items.append(item)
    _save(items)
    return len(items)


def add_many(new_items: list[dict[str, Any]], *, allow_duplicate: bool = False) -> int:
    items = _load()
    seen_urls = {item.get("url") for item in items}
    for item in new_items:
        url = item.get("url")
        if not allow_duplicate and url in seen_urls:
            continue
        items.append(item)
        seen_urls.add(url)
    _save(items)
    return len(items)


def list_items() -> list[dict[str, Any]]:
    return _load()


def get_item(index: int) -> dict[str, Any] | None:
    items = _load()
    if index < 1 or index > len(items):
        return None
    return items[index - 1]


def pop_next() -> dict[str, Any] | None:
    items = _load()
    if not items:
        return None
    item = items.pop(0)
    _save(items)
    return item


def remove(index: int) -> dict[str, Any] | None:
    items = _load()
    if index < 1 or index > len(items):
        return None
    item = items.pop(index - 1)
    _save(items)
    return item


def clear() -> int:
    items = _load()
    count = len(items)
    _save([])
    return count
