from __future__ import annotations

from radio_cli import player_settings


def test_volume_settings_round_trip(monkeypatch, tmp_path):
    settings_file = tmp_path / "player.settings.json"
    monkeypatch.setattr(player_settings, "PLAYER_SETTINGS_FILE", settings_file)
    monkeypatch.setattr(player_settings, "ensure_dirs", lambda: None)

    assert player_settings.load_volume() == 100.0
    assert player_settings.save_volume(35) == 35.0
    assert player_settings.load_volume() == 35.0
    assert player_settings.save_pre_pause_mute(True) is True
    assert player_settings.load_volume() == 35.0
    assert player_settings.load_pre_pause_mute() is True


def test_volume_settings_clamps_values(monkeypatch, tmp_path):
    settings_file = tmp_path / "player.settings.json"
    monkeypatch.setattr(player_settings, "PLAYER_SETTINGS_FILE", settings_file)
    monkeypatch.setattr(player_settings, "ensure_dirs", lambda: None)

    assert player_settings.save_volume(150) == 100.0
    assert player_settings.save_volume(-10) == 0.0


def test_mpv_set_volume_persists_preference(monkeypatch):
    from radio_cli import mpv_ipc

    calls = []
    monkeypatch.setattr(mpv_ipc, "set_property", lambda name, value: calls.append((name, value)))
    monkeypatch.setattr(mpv_ipc, "save_volume", lambda level: calls.append(("save", level)) or level)

    assert mpv_ipc.set_volume(42) == 42
    assert calls == [("volume", 42), ("save", 42)]


def test_toggle_pause_sets_inverse_pause_state(monkeypatch):
    from radio_cli import mpv_ipc

    calls = []
    monkeypatch.setattr(mpv_ipc, "get_property", lambda name: False)
    monkeypatch.setattr(mpv_ipc, "set_property", lambda name, value: calls.append((name, value)))
    monkeypatch.setattr(mpv_ipc, "save_pre_pause_mute", lambda muted: calls.append(("save_mute", muted)) or muted)

    assert mpv_ipc.toggle_pause() is True
    assert calls == [("save_mute", False), ("pause", True), ("mute", True)]


def test_toggle_pause_repairs_paused_but_unmuted_state(monkeypatch):
    from radio_cli import mpv_ipc

    calls = []
    monkeypatch.setattr(mpv_ipc, "get_property", lambda name: True if name == "pause" else False)
    monkeypatch.setattr(mpv_ipc, "set_property", lambda name, value: calls.append((name, value)))
    monkeypatch.setattr(mpv_ipc, "save_pre_pause_mute", lambda muted: calls.append(("save_mute", muted)) or muted)

    assert mpv_ipc.toggle_pause() is True
    assert calls == [("save_mute", False), ("mute", True)]


def test_toggle_pause_resumes_and_restores_previous_mute(monkeypatch):
    from radio_cli import mpv_ipc

    calls = []
    monkeypatch.setattr(mpv_ipc, "get_property", lambda name: True)
    monkeypatch.setattr(mpv_ipc, "set_property", lambda name, value: calls.append((name, value)))
    monkeypatch.setattr(mpv_ipc, "load_pre_pause_mute", lambda: False)

    assert mpv_ipc.toggle_pause() is False
    assert calls == [("pause", False), ("mute", False)]
