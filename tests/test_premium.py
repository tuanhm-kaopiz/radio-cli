from __future__ import annotations

import pytest

from radio_cli import premium


def test_parse_duration_defaults_to_minutes():
    assert premium.parse_duration_seconds("30") == 1800


def test_parse_duration_accepts_units():
    assert premium.parse_duration_seconds("90s") == 90
    assert premium.parse_duration_seconds("15m") == 900
    assert premium.parse_duration_seconds("1.5h") == 5400


def test_parse_duration_rejects_invalid_values():
    with pytest.raises(ValueError):
        premium.parse_duration_seconds("soon")
    with pytest.raises(ValueError):
        premium.parse_duration_seconds("0m")


def test_format_duration_prefers_clean_units():
    assert premium.format_duration(3600) == "1h"
    assert premium.format_duration(1800) == "30m"
    assert premium.format_duration(45) == "45s"
