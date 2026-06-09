from __future__ import annotations

import pytest

from radio_cli import ytdlp_util


def test_resolve_stream_url_non_youtube_is_unchanged():
    url = "https://example.com/track.mp3"
    assert ytdlp_util.resolve_stream_url(url, quiet=True) == url


def test_resolve_stream_url_quiet_raises_without_console(monkeypatch):
    monkeypatch.setattr(ytdlp_util, "_ytdlp_argv", lambda quiet=False: (_ for _ in ()).throw(ytdlp_util.YtdlpError("missing")))

    with pytest.raises(ytdlp_util.YtdlpError, match="missing"):
        ytdlp_util.resolve_stream_url("https://www.youtube.com/watch?v=abc", quiet=True)


def test_require_mpv_quiet_raises_without_console(monkeypatch):
    from radio_cli import player

    monkeypatch.setattr(player.shutil, "which", lambda name: None)

    with pytest.raises(player.PlayerError, match="Không tìm thấy mpv"):
        player.require_mpv(quiet=True)


def test_player_quiet_youtube_skips_console_status(monkeypatch):
    from radio_cli import player

    calls = []

    class FakeConsole:
        def status(self, *args, **kwargs):
            calls.append("status")
            raise AssertionError("console.status must not run in quiet mode")

        def print(self, *args, **kwargs):
            calls.append("print")

    monkeypatch.setattr(player, "console", FakeConsole())
    monkeypatch.setattr(player, "stop", lambda: None)
    monkeypatch.setattr(player, "is_youtube_url", lambda url: True)
    monkeypatch.setattr(player, "resolve_stream_url", lambda url, quiet=False: "https://cdn.example.com/audio.m4a")
    monkeypatch.setattr(player, "_mpv_cmd", lambda url, quiet=True: ["mpv", url])
    monkeypatch.setattr(player, "ensure_dirs", lambda: None)
    monkeypatch.setattr(player, "history", type("H", (), {"add": staticmethod(lambda **kwargs: None)})())
    monkeypatch.setattr(
        player.subprocess,
        "Popen",
        lambda *args, **kwargs: type("Proc", (), {"pid": 99, "poll": lambda self: None})(),
    )

    class _PidFile:
        def write_text(self, *args, **kwargs):
            return None

    monkeypatch.setattr(player, "PID_FILE", _PidFile())
    monkeypatch.setattr(player, "_write_state", lambda state: None)

    player.play(
        "https://www.youtube.com/watch?v=abc",
        title="Song",
        source="search",
        background=True,
        quiet=True,
    )

    assert calls == []


def test_player_quiet_background_raises_when_mpv_spawn_fails(monkeypatch):
    from radio_cli import player

    monkeypatch.setattr(player, "stop", lambda: None)
    monkeypatch.setattr(player, "is_youtube_url", lambda url: False)
    monkeypatch.setattr(player, "_mpv_cmd", lambda url, quiet=True: ["mpv", url])
    monkeypatch.setattr(player, "ensure_dirs", lambda: None)

    def fail_popen(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(player.subprocess, "Popen", fail_popen)

    with pytest.raises(player.PlayerError, match="Không thể chạy mpv"):
        player.play("https://example.com/a.mp3", title="Song", background=True, quiet=True)


def test_player_quiet_background_raises_when_mpv_exits_immediately(monkeypatch):
    from radio_cli import player

    class FakeProc:
        pid = 42

        def poll(self):
            return 1

    monkeypatch.setattr(player, "stop", lambda: None)
    monkeypatch.setattr(player, "is_youtube_url", lambda url: False)
    monkeypatch.setattr(player, "_mpv_cmd", lambda url, quiet=True: ["mpv", url])
    monkeypatch.setattr(player, "ensure_dirs", lambda: None)
    monkeypatch.setattr(player.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(player.subprocess, "Popen", lambda *args, **kwargs: FakeProc())

    with pytest.raises(player.PlayerError, match="mpv đã dừng"):
        player.play("https://example.com/a.mp3", title="Song", background=True, quiet=True)
