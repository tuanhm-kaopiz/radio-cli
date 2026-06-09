from __future__ import annotations

from radio_cli import history


def isolate_history(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(history, "ensure_dirs", lambda: None)


def test_remove_history_entry_by_index(monkeypatch, tmp_path):
    isolate_history(monkeypatch, tmp_path)
    history.add(title="One", url="https://example.com/1", source="url")
    history.add(title="Two", url="https://example.com/2", source="url")

    removed = history.remove(2)

    assert removed is not None
    assert removed["title"] == "One"
    assert [entry["title"] for entry in history.list_entries()] == ["Two"]


def test_remove_history_invalid_index_returns_none(monkeypatch, tmp_path):
    isolate_history(monkeypatch, tmp_path)

    assert history.remove(1) is None
