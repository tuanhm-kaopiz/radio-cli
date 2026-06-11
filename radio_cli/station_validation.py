from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from radio_cli.config import CATEGORIES
from radio_cli.stations import load_stations, stream_urls
from radio_cli.url_utils import UrlValidationError, validate_http_url


@dataclass
class StationValidationIssue:
    level: str
    station_id: str
    message: str


def validate_stations_data(items: list[dict[str, Any]] | None = None) -> list[StationValidationIssue]:
    stations = items if items is not None else load_stations()
    issues: list[StationValidationIssue] = []
    seen_ids: set[str] = set()
    seen_urls: dict[str, str] = {}

    for index, station in enumerate(stations, 1):
        station_id = str(station.get("id") or f"#{index}")
        name = str(station.get("name") or "")
        category = str(station.get("category") or "")
        primary_url = str(station.get("url") or "")

        if not station.get("id"):
            issues.append(StationValidationIssue("error", station_id, "Thiếu id."))
        elif station_id in seen_ids:
            issues.append(StationValidationIssue("error", station_id, "Trùng id."))
        seen_ids.add(station_id)

        if not name:
            issues.append(StationValidationIssue("error", station_id, "Thiếu name."))
        if category not in CATEGORIES:
            issues.append(StationValidationIssue("error", station_id, f"Category không hợp lệ: {category}"))

        try:
            validate_http_url(primary_url, field_name="url")
        except UrlValidationError as exc:
            issues.append(StationValidationIssue("error", station_id, str(exc)))

        for url in stream_urls(station):
            try:
                normalized_url = validate_http_url(str(url), field_name="stream URL")
            except UrlValidationError as exc:
                issues.append(StationValidationIssue("error", station_id, str(exc)))
                continue
            owner = seen_urls.get(normalized_url)
            if owner and owner != station_id:
                issues.append(StationValidationIssue("warning", station_id, f"URL trùng với {owner}."))
            seen_urls.setdefault(normalized_url, station_id)

        for field in ("tags", "aliases", "fallback_urls"):
            if not isinstance(station.get(field, []), list):
                issues.append(StationValidationIssue("error", station_id, f"{field} phải là list."))

    return issues
