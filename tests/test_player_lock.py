from __future__ import annotations

import threading
import time

from radio_cli import player
from radio_cli.player import PlayerError, _play_lock, play


def test_play_serializes_concurrent_background_starts(monkeypatch):
    active = 0
    max_active = 0
    counter_lock = threading.Lock()

    class FakeProc:
        pid = 1

        def poll(self):
            return None

        def wait(self):
            return 0

    def fake_popen(cmd, **kwargs):
        nonlocal active, max_active
        with counter_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with counter_lock:
            active -= 1
        return FakeProc()

    class _PidFile:
        def write_text(self, *args, **kwargs):
            return None

    monkeypatch.setattr(player, "stop", lambda: True)
    monkeypatch.setattr(player, "is_youtube_url", lambda url: False)
    monkeypatch.setattr(player, "_mpv_cmd", lambda url, quiet=True: ["mpv", url])
    monkeypatch.setattr(player, "ensure_dirs", lambda: None)
    monkeypatch.setattr(player, "_write_state", lambda state: None)
    monkeypatch.setattr(player, "PID_FILE", _PidFile())
    monkeypatch.setattr(player.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(player.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(player.history, "add", lambda **kwargs: None)

    errors: list[Exception] = []

    def run_play(url: str) -> None:
        try:
            play(url, title=url, background=True, quiet=True)
        except (PlayerError, SystemExit) as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run_play, args=(f"https://example.com/{index}",)) for index in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert not errors
    assert max_active == 1


def test_play_lock_is_not_held_after_success(monkeypatch):
    monkeypatch.setattr("radio_cli.player._play_locked", lambda *args, **kwargs: None)
    play("https://example.com/a", title="A", background=True, quiet=True)
    assert _play_lock.acquire(blocking=False)
    _play_lock.release()
