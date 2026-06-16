from __future__ import annotations

import json
import socket
import time
from typing import Any

from rich.console import Console

from radio_cli.config import IS_WINDOWS, IPC_SOCKET, mpv_ipc_server
from radio_cli.player_settings import load_pre_pause_mute, save_pre_pause_mute, save_volume
from radio_cli.player import get_playback_state

console = Console()

_IPC_RETRIES = 15
_IPC_RETRY_DELAY = 0.2


class MpvIpcError(Exception):
    pass


def _require_ipc() -> None:
    if get_playback_state() is None:
        raise MpvIpcError("Không có gì đang phát.")
    if not IS_WINDOWS and not IPC_SOCKET.exists():
        raise MpvIpcError("Player không hỗ trợ điều khiển (IPC socket không tồn tại).")


def _read_ipc_response(read_fn) -> str:
    chunks: list[bytes] = []
    while True:
        part = read_fn(4096)
        if not part:
            break
        chunks.append(part)
        if b"\n" in part:
            break
    return b"".join(chunks).decode().strip()


def _send_unix(payload: str) -> str:
    endpoint = mpv_ipc_server()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        sock.connect(endpoint)
        sock.sendall(payload.encode())
        return _read_ipc_response(sock.recv)


def _send_windows(payload: str) -> str:
    pipe_path = mpv_ipc_server()
    last_error: OSError | None = None
    for _ in range(_IPC_RETRIES):
        try:
            with open(pipe_path, "r+b", buffering=0) as pipe:
                pipe.write(payload.encode())
                return _read_ipc_response(pipe.read)
        except OSError as exc:
            last_error = exc
            time.sleep(_IPC_RETRY_DELAY)
    raise MpvIpcError(str(last_error or "Không kết nối được mpv named pipe"))


def send_command(*command: str | int | float | bool) -> dict[str, Any]:
    _require_ipc()
    payload = json.dumps({"command": list(command)}) + "\n"
    try:
        if IS_WINDOWS:
            raw = _send_windows(payload)
        else:
            raw = _send_unix(payload)
    except (OSError, socket.timeout) as exc:
        raise MpvIpcError(str(exc)) from exc

    if not raw:
        raise MpvIpcError("mpv IPC không phản hồi")

    try:
        return json.loads(raw.splitlines()[0])
    except json.JSONDecodeError as exc:
        raise MpvIpcError(f"Phản hồi IPC không hợp lệ: {raw}") from exc


def get_property(name: str) -> Any:
    resp = send_command("get_property", name)
    if resp.get("error") != "success":
        raise MpvIpcError(f"get_property {name} thất bại")
    return resp.get("data")


def set_property(name: str, value: Any) -> None:
    resp = send_command("set_property", name, value)
    if resp.get("error") != "success":
        raise MpvIpcError(f"set_property {name} thất bại")


def toggle_pause() -> bool:
    """Toggle pause; trả về True nếu đang pause sau lệnh."""
    paused = bool(get_property("pause"))
    muted = bool(get_property("mute"))
    if paused and not muted:
        save_pre_pause_mute(False)
        set_property("mute", True)
        return True
    next_paused = not paused
    if next_paused:
        save_pre_pause_mute(muted)
        set_property("pause", True)
        set_property("mute", True)
    else:
        set_property("pause", False)
        set_property("mute", load_pre_pause_mute())
    return next_paused


def get_volume() -> float:
    return float(get_property("volume") or 0)


def set_volume(level: float) -> float:
    level = max(0.0, min(100.0, level))
    set_property("volume", level)
    return save_volume(level)


def adjust_volume(delta: float) -> float:
    current = get_volume()
    return set_volume(current + delta)


def seek_relative(seconds: float) -> None:
    resp = send_command("seek", seconds, "relative")
    if resp.get("error") != "success":
        raise MpvIpcError("Không thể tua bài")


def seek_absolute(seconds: float) -> None:
    resp = send_command("seek", max(0.0, seconds), "absolute")
    if resp.get("error") != "success":
        raise MpvIpcError("Không thể tua bài")


def toggle_mute() -> bool:
    resp = send_command("cycle", "mute")
    if resp.get("error") != "success":
        raise MpvIpcError("Không thể mute/unmute")
    return bool(get_property("mute"))


def parse_volume_delta(value: str) -> float | None:
    value = value.strip()
    if not value.startswith(("+", "-")):
        return None
    try:
        return float(value)
    except ValueError:
        console.print(f"[red]Volume không hợp lệ: {value}[/red]")
        raise SystemExit(1) from None
