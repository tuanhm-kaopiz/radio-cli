from __future__ import annotations

from radio_cli.autoplay import AutoplayState, maybe_advance_queue, notify_manual_stop, notify_playback_started
from radio_cli.mpv_ipc import track_has_ended


def test_track_has_ended_on_eof(monkeypatch):
    monkeypatch.setattr("radio_cli.mpv_ipc.get_property", lambda name: True if name == "eof-reached" else None)
    assert track_has_ended() is True


def test_track_has_ended_near_duration_end(monkeypatch):
    def fake_get(name: str):
        if name == "eof-reached":
            return False
        if name == "duration":
            return 180.0
        if name == "time-pos":
            return 179.0
        return None

    monkeypatch.setattr("radio_cli.mpv_ipc.get_property", fake_get)
    assert track_has_ended() is True


def test_track_has_ended_false_for_live_stream(monkeypatch):
    monkeypatch.setattr(
        "radio_cli.mpv_ipc.get_property",
        lambda name: False if name == "eof-reached" else None,
    )
    assert track_has_ended() is False


def test_maybe_advance_queue_when_process_ends(monkeypatch):
    state = AutoplayState(last_seen_pid=123)
    played = []

    monkeypatch.setattr("radio_cli.autoplay.player.get_playback_state", lambda: None)
    monkeypatch.setattr(
        "radio_cli.autoplay.queue_store.pop_next",
        lambda: {"title": "Next", "url": "https://example.com/2", "source": "url"},
    )

    maybe_advance_queue(state, on_play=lambda item, *, subtitle: played.append((item["title"], subtitle)))
    assert played == [("Next", "Autoplay")]
    assert state.last_seen_pid is None


def test_maybe_advance_queue_on_eof(monkeypatch):
    state = AutoplayState()
    played = []
    stopped = []

    class FakeState:
        pid = 42

    monkeypatch.setattr("radio_cli.autoplay.player.get_playback_state", lambda: FakeState())
    monkeypatch.setattr("radio_cli.autoplay.track_has_ended", lambda: True)
    monkeypatch.setattr("radio_cli.autoplay.player.stop", lambda: stopped.append(True) or True)
    monkeypatch.setattr(
        "radio_cli.autoplay.queue_store.pop_next",
        lambda: {"title": "Next", "url": "https://example.com/2", "source": "url"},
    )

    maybe_advance_queue(state, on_play=lambda item, *, subtitle: played.append((item["title"], subtitle)))
    assert stopped == [True]
    assert played == [("Next", "Autoplay")]


def test_maybe_advance_respects_manual_stop(monkeypatch):
    state = AutoplayState(last_seen_pid=123)
    notify_manual_stop(state)
    played = []

    monkeypatch.setattr("radio_cli.autoplay.player.get_playback_state", lambda: None)
    monkeypatch.setattr(
        "radio_cli.autoplay.queue_store.pop_next",
        lambda: {"title": "Next", "url": "https://example.com/2", "source": "url"},
    )

    maybe_advance_queue(state, on_play=lambda item, *, subtitle: played.append(item))
    assert played == []


def test_notify_playback_started_clears_stop_flag():
    state = AutoplayState(stop_requested=True)
    notify_playback_started(state)
    assert state.stop_requested is False
