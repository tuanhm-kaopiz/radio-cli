from __future__ import annotations

import json
import unicodedata
from difflib import get_close_matches
from typing import Any

from radio_cli.config import CATEGORIES, STATIONS_FILE


def _text_key(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.lower().replace("-", " ").split())


def normalize_station(station: dict[str, Any]) -> dict[str, Any]:
    """Return a station object with v0.4 schema defaults filled in."""
    normalized = dict(station)
    normalized.setdefault("description", "")
    normalized.setdefault("frequency", "Online")
    normalized.setdefault("tags", [])
    normalized.setdefault("aliases", [])
    normalized.setdefault("country", "VN")
    normalized.setdefault("city", "")
    normalized.setdefault("homepage", "")

    fallback_urls = normalized.get("fallback_urls", [])
    if isinstance(fallback_urls, str):
        fallback_urls = [fallback_urls]
    normalized["fallback_urls"] = list(fallback_urls)
    return normalized


def load_stations() -> list[dict[str, Any]]:
    with STATIONS_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return [normalize_station(station) for station in data["stations"]]


def stream_urls(station: dict[str, Any]) -> list[str]:
    urls = [station["url"]]
    urls.extend(station.get("fallback_urls", []))
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url and url not in seen:
            unique.append(url)
            seen.add(url)
    return unique


def _match_fields(station: dict[str, Any]) -> list[str]:
    values = [
        station.get("id", ""),
        station.get("name", ""),
        station.get("category", ""),
        CATEGORIES.get(station.get("category", ""), ""),
        station.get("city", ""),
    ]
    values.extend(station.get("tags", []))
    values.extend(station.get("aliases", []))
    return [str(value) for value in values if value]


def resolve_station(query: str, stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    query_lower = query.lower().strip()
    query_key = _text_key(query)
    for station in stations:
        if station["id"].lower() == query_lower:
            return station
        aliases = [alias.lower() for alias in station.get("aliases", [])]
        if query_lower in aliases:
            return station

    matches = [
        station
        for station in stations
        if any(query_key in _text_key(field) for field in _match_fields(station))
    ]
    if len(matches) == 1:
        return matches[0]

    lookup: dict[str, dict[str, Any]] = {}
    choices: list[str] = []
    for station in stations:
        for field in _match_fields(station):
            key = _text_key(field)
            if key:
                lookup.setdefault(key, station)
                choices.append(key)
    close = get_close_matches(query_key, choices, n=2, cutoff=0.72)
    if len(close) == 1:
        return lookup[close[0]]
    return None


def filter_stations(
    stations: list[dict[str, Any]], category: str | None
) -> list[dict[str, Any]]:
    if not category:
        return stations
    cat_lower = category.lower().strip()
    cat_key = _text_key(category)
    if cat_lower in CATEGORIES:
        return [s for s in stations if s["category"] == cat_lower]
    return [
        s
        for s in stations
        if any(cat_key in _text_key(field) for field in _match_fields(s))
    ]


def station_by_id(station_id: str) -> dict[str, Any] | None:
    for station in load_stations():
        if station["id"] == station_id:
            return station
    return None
