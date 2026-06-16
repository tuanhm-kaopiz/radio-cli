from __future__ import annotations

from radio_cli import player


def test_get_running_pid_recovers_orphan_mpv(monkeypatch, tmp_path):
    pid_file = tmp_path / "player.pid"
    monkeypatch.setattr(player, "PID_FILE", pid_file)
    monkeypatch.setattr(player, "STATE_FILE", tmp_path / "player.state.json")
    monkeypatch.setattr(player, "IPC_SOCKET", tmp_path / "player.sock")
    pid_file.write_text("99999", encoding="utf-8")
    monkeypatch.setattr(player, "_pid_alive", lambda pid: pid == 4242)
    monkeypatch.setattr(player, "_discover_mpv_pids", lambda: [4242])

    assert player.get_running_pid() == 4242
    assert pid_file.read_text(encoding="utf-8") == "4242"


def test_stop_kills_discovered_mpv_even_without_pid_file(monkeypatch, tmp_path):
    killed: list[int] = []
    monkeypatch.setattr(player, "PID_FILE", tmp_path / "player.pid")
    monkeypatch.setattr(player, "STATE_FILE", tmp_path / "player.state.json")
    monkeypatch.setattr(player, "IPC_SOCKET", tmp_path / "player.sock")
    monkeypatch.setattr(player, "_discover_mpv_pids", lambda: [111, 222])
    monkeypatch.setattr(player, "_pid_alive", lambda pid: pid in {111, 222})
    monkeypatch.setattr(player, "_kill_pid", lambda pid: killed.append(pid))

    assert player.stop() is True
    assert killed == [111, 222]


def test_stop_returns_false_when_no_mpv_found(monkeypatch, tmp_path):
    monkeypatch.setattr(player, "PID_FILE", tmp_path / "player.pid")
    monkeypatch.setattr(player, "STATE_FILE", tmp_path / "player.state.json")
    monkeypatch.setattr(player, "IPC_SOCKET", tmp_path / "player.sock")
    monkeypatch.setattr(player, "_discover_mpv_pids", lambda: [])

    assert player.stop() is False


def test_get_playback_state_recovers_without_state_file(monkeypatch, tmp_path):
    pid_file = tmp_path / "player.pid"
    monkeypatch.setattr(player, "PID_FILE", pid_file)
    monkeypatch.setattr(player, "STATE_FILE", tmp_path / "player.state.json")
    monkeypatch.setattr(player, "IPC_SOCKET", tmp_path / "player.sock")
    monkeypatch.setattr(player, "_discover_mpv_pids", lambda: [4242])
    monkeypatch.setattr(player, "_pid_alive", lambda pid: True)

    state = player.get_playback_state()
    assert state is not None
    assert state.pid == 4242
    assert state.title == "(đang phát)"


def test_get_running_pid_prunes_extra_mpv_instances(monkeypatch, tmp_path):
    killed: list[int] = []
    pid_file = tmp_path / "player.pid"
    monkeypatch.setattr(player, "PID_FILE", pid_file)
    monkeypatch.setattr(player, "STATE_FILE", tmp_path / "player.state.json")
    monkeypatch.setattr(player, "IPC_SOCKET", tmp_path / "player.sock")
    monkeypatch.setattr(player, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(player, "_discover_mpv_pids", lambda: [100, 200])
    monkeypatch.setattr(player, "_kill_pid", lambda pid: killed.append(pid))

    assert player.get_running_pid() == 200
    assert killed == [100]
