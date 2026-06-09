from __future__ import annotations

from urllib.parse import urlparse


class UrlValidationError(ValueError):
    """Invalid external URL supplied by a user or feed."""


def validate_http_url(value: str, *, field_name: str = "URL") -> str:
    url = value.strip()
    if not url:
        raise UrlValidationError(f"{field_name} không được rỗng.")
    if any(char in url for char in "\r\n\t"):
        raise UrlValidationError(f"{field_name} không được chứa ký tự điều khiển.")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UrlValidationError(f"{field_name} phải là URL http/https hợp lệ.")
    return url


def is_http_url(value: str) -> bool:
    try:
        validate_http_url(value)
    except UrlValidationError:
        return False
    return True
