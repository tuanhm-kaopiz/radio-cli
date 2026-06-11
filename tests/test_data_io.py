from __future__ import annotations

import json

from radio_cli import data_io


def test_export_and_import_data(monkeypatch, tmp_path):
    files = {
        "favorites": tmp_path / "favorites.json",
        "history": tmp_path / "history.json",
        "queue": tmp_path / "queue.json",
        "audio_hub": tmp_path / "audio_hub.json",
    }
    monkeypatch.setattr(data_io, "DATA_FILES", files)
    monkeypatch.setattr(data_io, "ensure_dirs", lambda: None)
    files["favorites"].write_text(json.dumps({"stations": ["vov3"]}), encoding="utf-8")

    backup = tmp_path / "backup.json"
    data_io.export_data(backup)

    for path in files.values():
        path.unlink(missing_ok=True)

    imported = data_io.import_data(backup)

    assert imported == ["favorites", "history", "queue", "audio_hub"]
    assert json.loads(files["favorites"].read_text(encoding="utf-8")) == {"stations": ["vov3"]}
