from __future__ import annotations

from radio_cli import stations
from radio_cli.station_validation import validate_stations_data


def test_validate_stations_data_reports_duplicate_id_and_bad_url():
    items = [
        stations.normalize_station(
            {
                "id": "one",
                "name": "One",
                "category": "nhac-tre",
                "url": "https://example.com/one.m3u8",
            }
        ),
        stations.normalize_station(
            {
                "id": "one",
                "name": "Duplicate",
                "category": "bad",
                "url": "ftp://example.com/two.m3u8",
            }
        ),
    ]

    messages = [issue.message for issue in validate_stations_data(items)]

    assert "Trùng id." in messages
    assert any("Category không hợp lệ" in message for message in messages)
    assert any("http/https" in message for message in messages)
