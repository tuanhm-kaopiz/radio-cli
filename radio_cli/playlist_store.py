from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from radio_cli.config import PLAYLISTS_FILE, ensure_dirs
from radio_cli.url_utils import UrlValidationError, validate_http_url
from radio_cli.ytdlp_util import is_youtube_url

MAX_PLAYLISTS = 100
MAX_ITEMS_PER_PLAYLIST = 1000
_CSV_SKIP = object()


class PlaylistError(ValueError):
    pass


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "playlist"


def _load() -> list[dict[str, Any]]:
    ensure_dirs()
    if not PLAYLISTS_FILE.exists():
        return []
    try:
        data = json.loads(PLAYLISTS_FILE.read_text(encoding="utf-8"))
        playlists = data.get("playlists", [])
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(playlists, list):
        return []
    return [playlist for playlist in playlists if isinstance(playlist, dict)]


def _save(playlists: list[dict[str, Any]]) -> None:
    ensure_dirs()
    PLAYLISTS_FILE.write_text(
        json.dumps({"playlists": playlists[:MAX_PLAYLISTS]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _make_unique_id(name: str, playlists: list[dict[str, Any]]) -> str:
    existing = {playlist.get("id") for playlist in playlists}
    base = _slug(name)
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or item.get("url") or "Untitled")
    url = validate_http_url(str(item.get("url") or ""), field_name="Playlist URL")
    return {
        "title": title,
        "url": url,
        "source": item.get("source") or ("youtube" if is_youtube_url(url) else "url"),
        "added_at": float(item.get("added_at") or time.time()),
    }


def make_item(*, title: str, url: str) -> dict[str, Any]:
    url = validate_http_url(url, field_name="Playlist URL")
    return {
        "title": title.strip() or url,
        "url": url,
        "source": "youtube" if is_youtube_url(url) else "url",
        "added_at": time.time(),
    }


def _csv_fields(raw: str) -> list[str] | None:
    for delimiter in (",", ";", "\t"):
        if delimiter not in raw:
            continue
        try:
            fields = next(csv.reader([raw], delimiter=delimiter, skipinitialspace=True))
        except csv.Error:
            continue
        fields = [field.strip().lstrip("\ufeff") for field in fields]
        if len(fields) > 1:
            return fields
    return None


def _looks_like_csv_header(fields: list[str]) -> bool:
    normalized = {field.strip().lower().replace(" ", "_") for field in fields}
    return bool(normalized & {"url", "link", "links", "youtube_url", "video_url"}) and not any(
        _valid_url_field(field) for field in fields
    )


def _valid_url_field(field: str) -> str | None:
    try:
        return validate_http_url(field, field_name="Playlist URL")
    except UrlValidationError:
        return None


def _looks_like_row_number(value: str) -> bool:
    stripped = value.strip()
    return stripped.isdigit() or bool(re.fullmatch(r"\d+[.)]", stripped))


def _title_from_csv_fields(fields: list[str], url_index: int, url: str) -> str:
    before = [field for field in fields[:url_index] if field]
    after = [field for field in fields[url_index + 1 :] if field]
    meaningful_before = [field for field in before if not _looks_like_row_number(field)]
    if meaningful_before:
        return ", ".join(meaningful_before)
    if after:
        return after[0]
    if before:
        return before[-1]
    return url


def _parse_csv_import_line(raw: str) -> dict[str, Any] | object | None:
    fields = _csv_fields(raw)
    if fields is None:
        return None
    if _looks_like_csv_header(fields):
        return _CSV_SKIP
    for index, field in enumerate(fields):
        url = _valid_url_field(field)
        if url:
            return make_item(title=_title_from_csv_fields(fields, index, url), url=url)
    raise UrlValidationError("CSV import cần có một cột URL http/https hợp lệ.")


def create(name: str) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise PlaylistError("Tên playlist không được rỗng.")
    playlists = _load()
    existing = resolve(name, playlists)
    if existing is not None:
        return existing
    playlist = {
        "id": _make_unique_id(name, playlists),
        "name": name,
        "items": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    playlists.append(playlist)
    _save(playlists)
    return playlist


def list_playlists() -> list[dict[str, Any]]:
    return _load()


def resolve(name_or_id: str, playlists: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    normalized = name_or_id.strip().lower()
    slug = _slug(name_or_id)
    for playlist in playlists if playlists is not None else _load():
        if str(playlist.get("id", "")).lower() == normalized:
            return playlist
        if str(playlist.get("name", "")).lower() == normalized:
            return playlist
        if str(playlist.get("id", "")).lower() == slug:
            return playlist
    return None


def get(name_or_id: str) -> dict[str, Any] | None:
    playlist = resolve(name_or_id)
    if playlist is None:
        return None
    normalized = dict(playlist)
    normalized["items"] = [_normalize_item(item) for item in playlist.get("items", []) if isinstance(item, dict)]
    return normalized


def add_item(name_or_id: str, item: dict[str, Any], *, create_missing: bool = False) -> tuple[dict[str, Any], bool]:
    playlists = _load()
    playlist = resolve(name_or_id, playlists)
    if playlist is None:
        if not create_missing:
            raise PlaylistError(f"Không tìm thấy playlist: {name_or_id}")
        playlist = create(name_or_id)
        playlists = _load()
        playlist = resolve(name_or_id, playlists)
    if playlist is None:
        raise PlaylistError(f"Không tạo được playlist: {name_or_id}")

    normalized_item = _normalize_item(item)
    items = [_normalize_item(existing) for existing in playlist.get("items", []) if isinstance(existing, dict)]
    if any(existing["url"] == normalized_item["url"] for existing in items):
        playlist["items"] = items
        _save(playlists)
        return playlist, False

    items.append(normalized_item)
    playlist["items"] = items[:MAX_ITEMS_PER_PLAYLIST]
    playlist["updated_at"] = time.time()
    _save(playlists)
    return playlist, True


def parse_import_line(line: str) -> dict[str, Any] | None:
    raw = line.strip().lstrip("\ufeff")
    if not raw or raw.startswith("#"):
        return None
    try:
        url = validate_http_url(raw, field_name="Playlist URL")
    except UrlValidationError:
        csv_item = _parse_csv_import_line(raw)
        if csv_item is _CSV_SKIP:
            return None
        if csv_item is not None:
            if not isinstance(csv_item, dict):
                raise
            return csv_item
        if "|" in raw:
            title, url = raw.split("|", 1)
            return make_item(title=title.strip(), url=url.strip())
        raise
    return make_item(title=url, url=url)


def import_file(name_or_id: str, path: Path, *, create_missing: bool = False) -> tuple[int, int]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PlaylistError(f"Không đọc được file import: {exc}") from exc

    added = 0
    skipped = 0
    for line_no, line in enumerate(lines, 1):
        try:
            item = parse_import_line(line)
        except UrlValidationError as exc:
            raise PlaylistError(f"Dòng {line_no}: {exc}") from exc
        if item is None:
            continue
        _, did_add = add_item(name_or_id, item, create_missing=create_missing)
        if did_add:
            added += 1
        else:
            skipped += 1
    return added, skipped


def remove_item(name_or_id: str, index: int) -> dict[str, Any] | None:
    playlists = _load()
    playlist = resolve(name_or_id, playlists)
    if playlist is None:
        return None
    items = [_normalize_item(item) for item in playlist.get("items", []) if isinstance(item, dict)]
    if index < 1 or index > len(items):
        return None
    removed = items.pop(index - 1)
    playlist["items"] = items
    playlist["updated_at"] = time.time()
    _save(playlists)
    return removed


def rename(name_or_id: str, new_name: str) -> dict[str, Any]:
    new_name = new_name.strip()
    if not new_name:
        raise PlaylistError("Tên playlist không được rỗng.")
    playlists = _load()
    playlist = resolve(name_or_id, playlists)
    if playlist is None:
        raise PlaylistError(f"Không tìm thấy playlist: {name_or_id}")
    conflict = resolve(new_name, playlists)
    if conflict is not None and conflict.get("id") != playlist.get("id"):
        raise PlaylistError(f"Đã có playlist tên: {new_name}")
    playlist["name"] = new_name
    playlist["updated_at"] = time.time()
    _save(playlists)
    return playlist


def delete(name_or_id: str) -> dict[str, Any] | None:
    playlists = _load()
    for index, playlist in enumerate(playlists):
        if resolve(name_or_id, [playlist]) is not None:
            removed = playlists.pop(index)
            _save(playlists)
            return removed
    return None
