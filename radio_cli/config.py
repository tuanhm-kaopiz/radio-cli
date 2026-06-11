from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
STATIONS_FILE = PACKAGE_DIR / "data" / "stations.json"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IPC_PIPE_NAME = "radio-cli-mpv"


def _data_dir() -> Path:
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        return Path(local) / "radio-cli" if local else Path.home() / "radio-cli"
    return Path.home() / ".local" / "share" / "radio-cli"


def _config_dir() -> Path:
    if IS_WINDOWS:
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "radio-cli" if appdata else Path.home() / "radio-cli"
    return Path.home() / ".config" / "radio-cli"


DATA_DIR = _data_dir()
CONFIG_DIR = _config_dir()
PID_FILE = DATA_DIR / "player.pid"
STATE_FILE = DATA_DIR / "player.state.json"
IPC_SOCKET = DATA_DIR / "player.sock"  # Unix socket file (Linux/macOS)
HISTORY_FILE = DATA_DIR / "history.json"
QUEUE_FILE = DATA_DIR / "queue.json"
AUDIO_HUB_FILE = DATA_DIR / "audio_hub.json"
PLAYLISTS_FILE = DATA_DIR / "playlists.json"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"

CATEGORIES: dict[str, str] = {
    "nhac-tre": "Nhạc trẻ",
    "giai-tri": "Giải trí",
    "giao-thong": "Giao thông",
    "vpop": "V-Pop",
}


def mpv_ipc_server() -> str:
    """Đường dẫn IPC cho mpv: Unix socket (Linux/macOS) hoặc named pipe (Windows)."""
    if IS_WINDOWS:
        return rf"\\.\pipe\{IPC_PIPE_NAME}"
    return str(IPC_SOCKET)


def mpv_install_hint() -> str:
    if IS_WINDOWS:
        return "Tải mpv: https://mpv.io/installation/"
    if IS_MACOS:
        return "Cài đặt: brew install mpv"
    return "Cài đặt: sudo apt install mpv"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
