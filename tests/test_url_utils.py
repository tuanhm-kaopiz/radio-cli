from __future__ import annotations

import pytest

from radio_cli.url_utils import UrlValidationError, is_http_url, validate_http_url


def test_validate_http_url_accepts_and_strips_http_urls():
    assert validate_http_url(" https://example.com/radio.m3u8 ") == "https://example.com/radio.m3u8"


@pytest.mark.parametrize("url", ["", "ftp://example.com/file.mp3", "https:///missing-host", "https://exa\nmple.com"])
def test_validate_http_url_rejects_invalid_urls(url: str):
    with pytest.raises(UrlValidationError):
        validate_http_url(url)


def test_is_http_url_returns_boolean():
    assert is_http_url("https://example.com") is True
    assert is_http_url("file:///tmp/a.mp3") is False
