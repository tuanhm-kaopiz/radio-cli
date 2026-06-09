from __future__ import annotations

from radio_cli import queue_store
from radio_cli.tui import RadioTuiApp, _clip, _format_seconds, _progress_bar


def test_clip_short_text_is_unchanged():
    assert _clip("abc", 5) == "abc"


def test_clip_long_text_adds_ellipsis():
    assert _clip("abcdef", 4) == "abc…"


def test_format_seconds_and_progress_bar():
    assert _format_seconds(None) == "--:--"
    assert _format_seconds(65) == "1:05"
    assert _format_seconds(3661) == "1:01:01"
    assert _progress_bar(5, 10, width=10) == "━━━━━─────"
    assert _progress_bar(None, None, width=4) == "────"


def test_tui_app_initial_state():
    app = RadioTuiApp()

    assert app.active_pane == "stations"
    assert app.cursors == {"stations": 0, "search": 0, "queue": 0, "history": 0}


def test_shortcut_panel_contains_core_keys():
    app = RadioTuiApp()
    panel = app._shortcut_panel()
    body = str(panel.renderable)

    assert "Tab/l" in body
    assert "Shift+Tab/h" in body
    assert "/ search" in body
    assert "Esc" in body
    assert "d/x/Delete" in body
    assert "Space" in body
    assert "q" in body


def test_panel_navigation_actions(monkeypatch):
    app = RadioTuiApp()
    monkeypatch.setattr(app, "refresh_ui", lambda: None)

    app.action_next_pane()
    assert app.active_pane == "search"

    app.action_next_pane()
    assert app.active_pane == "queue"

    app.action_previous_pane()
    assert app.active_pane == "search"


def test_delete_selected_removes_queue_item(monkeypatch):
    items = [
        {"title": "One", "url": "https://example.com/1", "source": "url"},
        {"title": "Two", "url": "https://example.com/2", "source": "url"},
    ]

    def fake_list_items():
        return list(items)

    def fake_remove(index: int):
        if index < 1 or index > len(items):
            return None
        return items.pop(index - 1)

    monkeypatch.setattr(queue_store, "list_items", fake_list_items)
    monkeypatch.setattr(queue_store, "remove", fake_remove)

    app = RadioTuiApp()
    app.active_pane = "queue"
    app.cursors["queue"] = 1
    monkeypatch.setattr(app, "refresh_ui", lambda: None)

    app.action_delete_selected()

    assert [item["title"] for item in items] == ["One"]
    assert app.cursors["queue"] == 0
    assert "Đã xóa khỏi queue: Two" == app._message


def test_finish_search_sets_results(monkeypatch):
    app = RadioTuiApp()
    monkeypatch.setattr(app, "refresh_ui", lambda: None)

    app._finish_search(
        "demo",
        [{"title": "Song", "url": "https://youtube.com/watch?v=1", "source": "search", "duration": "3:00"}],
        None,
    )

    assert app.search_results[0]["title"] == "Song"
    assert app.active_pane == "search"
    assert app._message == "Tìm thấy 1 kết quả cho: demo"


def test_delete_selected_removes_history_item(monkeypatch):
    items = [
        {"title": "One", "url": "https://example.com/1", "source": "url"},
        {"title": "Two", "url": "https://example.com/2", "source": "url"},
    ]

    def fake_list_entries():
        return list(items)

    def fake_remove(index: int):
        if index < 1 or index > len(items):
            return None
        return items.pop(index - 1)

    monkeypatch.setattr("radio_cli.tui.history.list_entries", fake_list_entries)
    monkeypatch.setattr("radio_cli.tui.history.remove", fake_remove)

    app = RadioTuiApp()
    app.active_pane = "history"
    app.cursors["history"] = 1
    monkeypatch.setattr(app, "refresh_ui", lambda: None)

    app.action_delete_selected()

    assert [item["title"] for item in items] == ["One"]
    assert app.cursors["history"] == 0
    assert "Đã xóa khỏi history: Two" == app._message


def test_play_search_starts_background_worker(monkeypatch):
    app = RadioTuiApp()
    app.search_results = [
        {"title": "Song", "url": "https://youtube.com/watch?v=1", "source": "search", "duration": "3:00"}
    ]
    app.active_pane = "search"
    monkeypatch.setattr(app, "refresh_ui", lambda: None)
    started = []

    class FakeThread:
        def __init__(self, target, args=(), daemon=False):
            self._target = target
            self._args = args

        def start(self):
            started.append(self._args)
            self._target(*self._args)

    monkeypatch.setattr("radio_cli.tui.threading.Thread", FakeThread)
    monkeypatch.setattr(app, "_start_playback", lambda item: "Song")
    monkeypatch.setattr(app, "call_from_thread", lambda callback, *args: callback(*args))

    app.action_play_selected()

    assert started == [({"title": "Song", "url": "https://youtube.com/watch?v=1", "source": "search", "duration": "3:00"}, "Đang phát")]
    assert app._message == "Đang phát: Song"
    assert app.active_pane == "search"


def test_play_search_error_stays_in_tui(monkeypatch):
    app = RadioTuiApp()
    app.search_results = [
        {"title": "Song", "url": "https://youtube.com/watch?v=1", "source": "search", "duration": "3:00"}
    ]
    app.active_pane = "search"
    monkeypatch.setattr(app, "refresh_ui", lambda: None)

    class FakeThread:
        def __init__(self, target, args=(), daemon=False):
            self._target = target
            self._args = args

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr("radio_cli.tui.threading.Thread", FakeThread)
    monkeypatch.setattr(app, "call_from_thread", lambda callback, *args: callback(*args))

    def fail_play(*args, **kwargs):
        raise RuntimeError("Không lấy được stream YouTube.")

    monkeypatch.setattr("radio_cli.tui.player.play", fail_play)

    app.action_play_selected()

    assert app._message.startswith("Lỗi phát:")
    assert app.active_pane == "search"


def test_now_panel_survives_ipc_errors(monkeypatch):
    from radio_cli.player import PlaybackState

    from radio_cli import mpv_ipc

    monkeypatch.setattr(
        "radio_cli.tui.player.get_playback_state",
        lambda: PlaybackState(title="Song", source="url", url="https://example.com/a.mp3", pid=42),
    )

    def fail_ipc(*args, **kwargs):
        raise mpv_ipc.MpvIpcError("IPC socket chưa sẵn sàng")

    monkeypatch.setattr("radio_cli.tui.get_property", fail_ipc)
    monkeypatch.setattr("radio_cli.tui.get_volume", fail_ipc)

    app = RadioTuiApp()
    panel = app._now_panel()

    assert "Song" in str(panel.renderable)


def test_search_worker_uses_quiet_search(monkeypatch):
    app = RadioTuiApp()
    calls = []

    def fake_search(query, limit=8, quiet=False):
        calls.append({"query": query, "limit": limit, "quiet": quiet})
        return []

    monkeypatch.setattr("radio_cli.tui.search_module.search_vpop", fake_search)
    monkeypatch.setattr(app, "refresh_ui", lambda: None)
    monkeypatch.setattr(app, "call_from_thread", lambda callback, *args: callback(*args))

    app._search_worker("demo")

    assert calls == [{"query": "demo", "limit": 8, "quiet": True}]


def test_play_queue_item_uses_quiet_background(monkeypatch):
    app = RadioTuiApp()
    app.active_pane = "queue"
    calls = []

    monkeypatch.setattr(
        queue_store,
        "list_items",
        lambda: [{"title": "Queued Song", "url": "https://example.com/a.mp3", "source": "url"}],
    )
    monkeypatch.setattr(queue_store, "remove", lambda index: queue_store.list_items()[index - 1])
    monkeypatch.setattr(app, "refresh_ui", lambda: None)

    def fake_play(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("radio_cli.tui.player.play", fake_play)

    app.action_play_selected()

    assert calls == [
        {
            "title": "Queued Song",
            "source": "url",
            "station_id": None,
            "background": True,
            "quiet": True,
        }
    ]
    assert app._message.startswith("Đang phát từ queue:")


def test_autoplay_next_uses_queue_when_track_ends(monkeypatch):
    app = RadioTuiApp()
    app._last_seen_pid = 123
    app._stop_requested = False
    played = []

    monkeypatch.setattr("radio_cli.tui.player.get_playback_state", lambda: None)
    monkeypatch.setattr(
        "radio_cli.tui.queue_store.pop_next",
        lambda: {"title": "Next Song", "url": "https://youtube.com/watch?v=2", "source": "search"},
    )

    def fake_play_item(item, *, subtitle):
        played.append((item["title"], subtitle))

    monkeypatch.setattr(app, "_play_item", fake_play_item)

    app._maybe_autoplay_next()

    assert played == [("Next Song", "Autoplay")]
    assert app._last_seen_pid is None
