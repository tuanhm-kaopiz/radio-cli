from __future__ import annotations

import json

from radio_cli.config import PLAYER_SETTINGS_FILE, ensure_dirs

DEFAULT_VOLUME = 100.0


def _load_settings() -> dict:
    if not PLAYER_SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(PLAYER_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_settings(data: dict) -> None:
    ensure_dirs()
    PLAYER_SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clamp_volume(level: float) -> float:
    return max(0.0, min(100.0, level))


def load_volume() -> float:
    data = _load_settings()
    try:
        return _clamp_volume(float(data.get("volume", DEFAULT_VOLUME)))
    except (TypeError, ValueError):
        return DEFAULT_VOLUME


def save_volume(level: float) -> float:
    volume = _clamp_volume(level)
    data = _load_settings()
    data["volume"] = volume
    _save_settings(data)
    return volume


def load_pre_pause_mute() -> bool:
    data = _load_settings()
    return bool(data.get("pre_pause_mute", False))


def save_pre_pause_mute(muted: bool) -> bool:
    data = _load_settings()
    data["pre_pause_mute"] = bool(muted)
    _save_settings(data)
    return bool(muted)
