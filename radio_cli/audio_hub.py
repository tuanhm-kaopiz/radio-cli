from __future__ import annotations

import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Literal

from radio_cli.config import AUDIO_HUB_FILE, ensure_dirs
from radio_cli.url_utils import validate_http_url

HubKind = Literal["podcast", "story", "broadcast"]
MAX_FEEDS = 100


def _load() -> dict[str, Any]:
    ensure_dirs()
    if not AUDIO_HUB_FILE.exists():
        return {"feeds": []}
    try:
        data = json.loads(AUDIO_HUB_FILE.read_text(encoding="utf-8"))
        return {"feeds": list(data.get("feeds", []))}
    except (json.JSONDecodeError, OSError):
        return {"feeds": []}


def _save(data: dict[str, Any]) -> None:
    ensure_dirs()
    data["feeds"] = list(data.get("feeds", []))[:MAX_FEEDS]
    AUDIO_HUB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "feed"


def _unique_id(base: str, feeds: list[dict[str, Any]]) -> str:
    existing = {feed.get("id") for feed in feeds}
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def add_feed(*, name: str, rss_url: str, kind: HubKind = "podcast") -> dict[str, Any]:
    if kind not in {"podcast", "story", "broadcast"}:
        raise ValueError(f"Loại audio không hợp lệ: {kind}")
    rss_url = validate_http_url(rss_url, field_name="RSS URL")
    data = _load()
    feeds = data["feeds"]
    for feed in feeds:
        if feed.get("rss_url") == rss_url:
            return feed
    feed = {
        "id": _unique_id(_slug(name), feeds),
        "name": name,
        "rss_url": rss_url,
        "kind": kind,
        "added_at": time.time(),
    }
    feeds.append(feed)
    _save(data)
    return feed


def list_feeds(kind: HubKind | None = None) -> list[dict[str, Any]]:
    feeds = _load()["feeds"]
    if kind is None:
        return feeds
    return [feed for feed in feeds if feed.get("kind") == kind]


def get_feed(feed_id: str) -> dict[str, Any] | None:
    normalized = feed_id.strip().lower()
    for feed in list_feeds():
        if feed.get("id") == normalized or feed.get("name", "").lower() == normalized:
            return feed
    return None


def remove_feed(feed_id: str) -> dict[str, Any] | None:
    data = _load()
    feeds = data["feeds"]
    for index, feed in enumerate(feeds):
        if feed.get("id") == feed_id:
            removed = feeds.pop(index)
            _save(data)
            return removed
    return None


def _text(node: ET.Element | None) -> str:
    return "" if node is None or node.text is None else node.text.strip()


def _first_text(item: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        found = item.find(name)
        if found is not None and found.text:
            return found.text.strip()
    for child in item:
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in {name.lower() for name in names} and child.text:
            return child.text.strip()
    return ""


def _episode_url(item: ET.Element) -> str:
    enclosure = item.find("enclosure")
    if enclosure is not None and enclosure.get("url"):
        return enclosure.get("url", "").strip()
    for child in item:
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local == "enclosure" and child.get("url"):
            return child.get("url", "").strip()
    return _first_text(item, ("link", "guid"))


def fetch_episodes(feed: dict[str, Any], *, limit: int = 20, timeout: int = 20) -> list[dict[str, Any]]:
    rss_url = validate_http_url(str(feed["rss_url"]), field_name="RSS URL")
    request = urllib.request.Request(rss_url, headers={"User-Agent": "radio-cli-audio-hub/0.7"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    if channel is None:
        channel = root
    episodes: list[dict[str, Any]] = []
    for item in channel.findall("item")[:limit]:
        try:
            url = validate_http_url(_episode_url(item), field_name="Episode URL")
        except ValueError:
            continue
        title = _first_text(item, ("title",)) or url
        episodes.append(
            {
                "title": title,
                "url": url,
                "source": feed.get("kind", "podcast"),
                "feed_id": feed.get("id"),
                "feed_name": feed.get("name"),
                "published": _first_text(item, ("pubDate", "published")),
                "duration": _first_text(item, ("duration",)),
            }
        )
    return episodes


def get_episode(feed_id: str, index: int) -> dict[str, Any] | None:
    feed = get_feed(feed_id)
    if feed is None:
        return None
    episodes = fetch_episodes(feed, limit=max(index, 1))
    if index < 1 or index > len(episodes):
        return None
    return episodes[index - 1]
