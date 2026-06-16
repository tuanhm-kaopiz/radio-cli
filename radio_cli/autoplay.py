from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol


class PlayCallback(Protocol):
    def __call__(self, item: dict[str, Any], *, subtitle: str) -> None: ...

from radio_cli import player, queue_store
from radio_cli.mpv_ipc import track_has_ended
from radio_cli.player import PlayerError

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1.5


@dataclass
class AutoplayState:
    last_seen_pid: int | None = None
    stop_requested: bool = False


def notify_playback_started(state: AutoplayState) -> None:
    state.stop_requested = False


def notify_manual_stop(state: AutoplayState) -> None:
    state.stop_requested = True
    state.last_seen_pid = None


def maybe_advance_queue(
    state: AutoplayState,
    *,
    on_play: PlayCallback,
    on_message: Callable[[str], None] | None = None,
) -> None:
    if state.stop_requested:
        return

    playback = player.get_playback_state()
    ended = False

    if playback is not None:
        state.last_seen_pid = playback.pid
        ended = track_has_ended()
        if not ended:
            return
        player.stop()
    elif state.last_seen_pid is not None:
        ended = True
    else:
        return

    if state.last_seen_pid is None:
        return

    state.last_seen_pid = None
    next_item = queue_store.pop_next()
    if next_item is None:
        if on_message:
            on_message("Bài đã kết thúc. Queue trống.")
        return
    on_play(next_item, subtitle="Autoplay")


def _play_item_background(item: dict[str, Any]) -> None:
    from radio_cli import stations

    try:
        if item.get("source") == "station" and item.get("station_id"):
            station = stations.station_by_id(item["station_id"])
            if station:
                player.play(
                    station["url"],
                    title=station["name"],
                    source="station",
                    station_id=station["id"],
                    background=True,
                    quiet=True,
                )
                notify_playback_started(_cli_state)
                return
        player.play(
            item["url"],
            title=item["title"],
            source=item.get("source", "url"),
            station_id=item.get("station_id"),
            background=True,
            quiet=True,
        )
        notify_playback_started(_cli_state)
    except PlayerError:
        logger.warning("Autoplay failed for %s", item.get("title", "—"))


_cli_state = AutoplayState()
_watcher_started = False
_watcher_lock = threading.Lock()


def _cli_watcher_loop() -> None:
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            maybe_advance_queue(
                _cli_state,
                on_play=lambda item, _subtitle: _play_item_background(item),
            )
        except Exception:
            logger.exception("CLI autoplay watcher error")


def ensure_cli_watcher() -> None:
    global _watcher_started
    with _watcher_lock:
        if _watcher_started:
            return
        _watcher_started = True
        threading.Thread(target=_cli_watcher_loop, daemon=True, name="radio-cli-autoplay").start()


def notify_cli_playback_started() -> None:
    notify_playback_started(_cli_state)
    ensure_cli_watcher()


def notify_cli_manual_stop() -> None:
    notify_manual_stop(_cli_state)
