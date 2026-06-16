from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from rich.console import Console

from radio_cli import history
from radio_cli.config import (
    IPC_SOCKET,
    IS_WINDOWS,
    PID_FILE,
    STATE_FILE,
    ensure_dirs,
    mpv_install_hint,
    mpv_ipc_server,
)
from radio_cli.player_settings import load_volume
from radio_cli.ytdlp_util import YtdlpError, is_youtube_url, resolve_stream_url

console = Console()
logger = logging.getLogger(__name__)


class PlayerError(Exception):
    """Lỗi player không ghi ra terminal (dùng từ TUI)."""


@dataclass
class PlaybackState:
    title: str
    source: str  # station | search | url
    url: str
    station_id: str | None = None
    pid: int | None = None
    started_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "station_id": self.station_id,
            "pid": self.pid,
            "started_at": time.time(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlaybackState:
        return cls(
            title=data["title"],
            source=data["source"],
            url=data["url"],
            station_id=data.get("station_id"),
            pid=data.get("pid"),
            started_at=data.get("started_at"),
        )


def is_live_station(state: PlaybackState) -> bool:
    """Radio stream từ stations.json (01–06) — không có duration cố định."""
    return state.source == "station"


def live_elapsed_seconds(state: PlaybackState) -> float:
    started = state.started_at or time.time()
    return max(0.0, time.time() - started)


def require_mpv(*, quiet: bool = False) -> str:
    mpv = shutil.which("mpv")
    if not mpv:
        message = f"Không tìm thấy mpv. {mpv_install_hint()}"
        if quiet:
            raise PlayerError(message)
        console.print(f"[red]{message}[/red]")
        raise SystemExit(1)
    return mpv


def _read_state_file() -> dict[str, Any] | None:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_state(state: PlaybackState) -> None:
    ensure_dirs()
    STATE_FILE.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clear_state() -> None:
    for path in (PID_FILE, STATE_FILE):
        if path.exists():
            path.unlink()
    if not IS_WINDOWS and IPC_SOCKET.exists():
        IPC_SOCKET.unlink()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_running_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        _clear_state()
        return None
    if _pid_alive(pid):
        return pid
    _clear_state()
    return None


def get_playback_state() -> PlaybackState | None:
    pid = get_running_pid()
    if pid is None:
        return None
    data = _read_state_file()
    if not data:
        return None
    state = PlaybackState.from_dict(data)
    state.pid = pid
    return state


def stop(background_only: bool = False) -> bool:
    pid = get_running_pid()
    if pid is None:
        return False
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not _pid_alive(pid):
                    break
                time.sleep(0.1)
            if _pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    _clear_state()
    return True


def _prepare_ipc_endpoint() -> None:
    ensure_dirs()
    if not IS_WINDOWS and IPC_SOCKET.exists():
        IPC_SOCKET.unlink()


def _subprocess_kwargs(background: bool) -> dict:
    """Tùy chọn spawn process theo nền tảng."""
    if not background:
        return {}
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    return kwargs


def _mpv_cmd(url: str, *, quiet: bool = True) -> list[str]:
    mpv = require_mpv(quiet=quiet)
    _prepare_ipc_endpoint()
    cmd = [
        mpv,
        "--no-video",
        f"--volume={load_volume():.0f}",
        f"--input-ipc-server={mpv_ipc_server()}",
    ]
    if quiet:
        cmd.extend(["--really-quiet", "--msg-level=all=error"])
    cmd.append(url)
    return cmd


def play(
    url: str,
    *,
    title: str,
    source: str = "url",
    station_id: str | None = None,
    background: bool = False,
    quiet: bool = True,
    fallback_urls: list[str] | None = None,
) -> None:
    """Phát audio. Foreground chặn terminal; background detach process."""
    stop()

    candidate_urls = [url]
    for fallback_url in fallback_urls or []:
        if fallback_url and fallback_url not in candidate_urls:
            candidate_urls.append(fallback_url)

    last_error: PlayerError | None = None
    for index, candidate_url in enumerate(candidate_urls):
        try:
            _play_candidate(
                candidate_url,
                original_url=url,
                title=title,
                source=source,
                station_id=station_id,
                background=background,
                quiet=quiet,
            )
            return
        except PlayerError as exc:
            last_error = exc
            logger.debug("Playback candidate failed: %s", candidate_url, exc_info=True)
            if index + 1 < len(candidate_urls):
                if not quiet:
                    console.print("[yellow]Stream lỗi, thử fallback tiếp theo...[/yellow]")
                continue
            break

    if last_error is not None:
        if quiet:
            raise last_error
        console.print(f"[red]{last_error}[/red]")
        raise SystemExit(1)


def _play_candidate(
    play_url: str,
    *,
    original_url: str,
    title: str,
    source: str,
    station_id: str | None,
    background: bool,
    quiet: bool,
) -> None:
    if is_youtube_url(play_url):
        try:
            if quiet:
                play_url = resolve_stream_url(play_url, quiet=True)
            else:
                with console.status("[bold]Đang lấy stream audio...[/bold]"):
                    play_url = resolve_stream_url(play_url)
        except YtdlpError as exc:
            raise PlayerError(str(exc)) from exc

    cmd = _mpv_cmd(play_url, quiet=quiet)
    state = PlaybackState(title=title, source=source, url=original_url, station_id=station_id)

    if background:
        ensure_dirs()
        try:
            proc = subprocess.Popen(cmd, **_subprocess_kwargs(background=True))
        except OSError as exc:
            raise PlayerError(f"Không thể chạy mpv: {exc}") from exc
        time.sleep(0.2)
        if proc.poll() is not None:
            raise PlayerError("mpv đã dừng ngay sau khi mở. Kiểm tra URL stream hoặc kết nối mạng.")
        state.pid = proc.pid
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        _write_state(state)
        history.add(title=title, url=original_url, source=source, station_id=station_id)
        if not quiet:
            console.print(f"[green]▶[/green] Đang phát nền: [bold]{title}[/bold] (pid {proc.pid})")
            console.print(
                "[dim]Dùng [bold]radio stop[/bold] · [bold]radio pause[/bold] · [bold]radio vol 70[/bold][/dim]"
            )
        return

    try:
        proc = subprocess.Popen(cmd)
    except OSError as exc:
        raise PlayerError(f"Không thể chạy mpv: {exc}") from exc
    state.pid = proc.pid
    _write_state(state)
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    history.add(title=title, url=original_url, source=source, station_id=station_id)

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
    finally:
        if get_running_pid() == proc.pid:
            _clear_state()

    if proc.returncode not in (0, -15, 255):
        raise PlayerError("Không thể phát. Kiểm tra kết nối mạng hoặc URL.")
