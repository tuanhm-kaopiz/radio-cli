from __future__ import annotations

from radio_cli import stations
from radio_cli.config import STATIONS_FILE


def sample_stations():
    return [
        stations.normalize_station(
            {
                "id": "vov-gt-hn",
                "name": "VOV Giao Thông Hà Nội",
                "category": "giao-thong",
                "url": "https://example.com/hn.m3u8",
                "tags": ["traffic", "hanoi"],
                "aliases": ["giao thong ha noi"],
                "fallback_urls": ["https://fallback.example.com/hn.m3u8"],
            }
        ),
        stations.normalize_station(
            {
                "id": "vov3",
                "name": "VOV3 - Âm nhạc & Sự kiện",
                "category": "nhac-tre",
                "url": "https://example.com/vov3.m3u8",
                "tags": ["vpop", "music"],
                "aliases": ["vov music"],
            }
        ),
    ]


def test_normalize_station_adds_v04_defaults():
    station = stations.normalize_station(
        {"id": "demo", "name": "Demo", "category": "nhac-tre", "url": "https://example.com"}
    )

    assert station["description"] == ""
    assert station["frequency"] == "Online"
    assert station["tags"] == []
    assert station["aliases"] == []
    assert station["fallback_urls"] == []
    assert station["country"] == "VN"


def test_packaged_stations_file_is_inside_package():
    assert STATIONS_FILE.name == "stations.json"
    assert STATIONS_FILE.parent.name == "data"
    assert STATIONS_FILE.exists()
    assert stations.load_stations()


def test_resolve_station_matches_accentless_alias():
    resolved = stations.resolve_station("giao thong ha noi", sample_stations())

    assert resolved is not None
    assert resolved["id"] == "vov-gt-hn"


def test_resolve_station_matches_close_name():
    resolved = stations.resolve_station("vov musc", sample_stations())

    assert resolved is not None
    assert resolved["id"] == "vov3"


def test_filter_stations_matches_tag():
    filtered = stations.filter_stations(sample_stations(), "traffic")

    assert [station["id"] for station in filtered] == ["vov-gt-hn"]


def test_stream_urls_deduplicates_primary_and_fallbacks():
    station = stations.normalize_station(
        {
            "id": "demo",
            "name": "Demo",
            "category": "nhac-tre",
            "url": "https://example.com/a",
            "fallback_urls": ["https://example.com/a", "https://example.com/b"],
        }
    )

    assert stations.stream_urls(station) == ["https://example.com/a", "https://example.com/b"]


def test_resolve_station_handles_vietnamese_d():
    items = [
        stations.normalize_station(
            {
                "id": "vov5",
                "name": "VOV5 - Phát thanh đối ngoại",
                "category": "giai-tri",
                "url": "https://example.com/vov5.m3u8",
            }
        )
    ]

    resolved = stations.resolve_station("doi ngoai", items)

    assert resolved is not None
    assert resolved["id"] == "vov5"
