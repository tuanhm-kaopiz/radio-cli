from __future__ import annotations

import pytest

from radio_cli import playlist_store


def isolate_playlists(monkeypatch, tmp_path):
    monkeypatch.setattr(playlist_store, "PLAYLISTS_FILE", tmp_path / "playlists.json")
    monkeypatch.setattr(playlist_store, "ensure_dirs", lambda: None)


def test_create_add_show_and_remove_playlist_item(monkeypatch, tmp_path):
    isolate_playlists(monkeypatch, tmp_path)

    playlist = playlist_store.create("Danh sách yêu thích 1")
    playlist, added = playlist_store.add_item(
        playlist["id"],
        playlist_store.make_item(title="Song One", url="https://www.youtube.com/watch?v=abc123"),
    )
    _, duplicate_added = playlist_store.add_item(
        playlist["id"],
        playlist_store.make_item(title="Song One again", url="https://www.youtube.com/watch?v=abc123"),
    )

    loaded = playlist_store.get("Danh sách yêu thích 1")
    removed = playlist_store.remove_item("Danh sách yêu thích 1", 1)

    assert playlist["id"] == "danh-sach-yeu-thich-1"
    assert added is True
    assert duplicate_added is False
    assert loaded is not None
    assert loaded["items"][0]["title"] == "Song One"
    assert removed is not None
    assert playlist_store.get("Danh sách yêu thích 1")["items"] == []


def test_import_file_supports_title_pipe_url_and_skips_duplicates(monkeypatch, tmp_path):
    isolate_playlists(monkeypatch, tmp_path)
    links = tmp_path / "links.txt"
    links.write_text(
        "\n".join(
            [
                "# comment",
                "Song A | https://youtu.be/abc123",
                "https://www.youtube.com/watch?v=def456",
                "Song A duplicate | https://youtu.be/abc123",
            ]
        ),
        encoding="utf-8",
    )

    added, skipped = playlist_store.import_file("Danh sách yêu thích 1", links, create_missing=True)
    playlist = playlist_store.get("danh-sach-yeu-thich-1")

    assert (added, skipped) == (2, 1)
    assert playlist is not None
    assert [item["title"] for item in playlist["items"]] == ["Song A", "https://www.youtube.com/watch?v=def456"]


def test_import_file_supports_csv_with_header_and_url_column(monkeypatch, tmp_path):
    isolate_playlists(monkeypatch, tmp_path)
    links = tmp_path / "links.csv"
    links.write_text(
        "\n".join(
            [
                "title,url",
                "Song A,https://music.youtube.com/watch?v=abc123",
                "1,Song B,https://www.youtube.com/live/def456?si=share",
                '"https://m.youtube.com/watch?v=ghi789","Song C"',
            ]
        ),
        encoding="utf-8",
    )

    added, skipped = playlist_store.import_file("CSV Playlist", links, create_missing=True)
    playlist = playlist_store.get("CSV Playlist")

    assert (added, skipped) == (3, 0)
    assert playlist is not None
    assert [item["title"] for item in playlist["items"]] == ["Song A", "Song B", "Song C"]
    assert [item["source"] for item in playlist["items"]] == ["youtube", "youtube", "youtube"]


def test_rename_playlist_updates_name(monkeypatch, tmp_path):
    isolate_playlists(monkeypatch, tmp_path)

    playlist = playlist_store.create("Old Name")
    renamed = playlist_store.rename(playlist["id"], "New Name")

    assert renamed["name"] == "New Name"
    assert renamed["id"] == playlist["id"]
    loaded = playlist_store.get("New Name")
    assert loaded is not None
    assert loaded["name"] == "New Name"


def test_rename_rejects_duplicate_name(monkeypatch, tmp_path):
    isolate_playlists(monkeypatch, tmp_path)

    playlist_store.create("First")
    second = playlist_store.create("Second")

    with pytest.raises(playlist_store.PlaylistError, match="Đã có playlist"):
        playlist_store.rename(second["id"], "First")


def test_import_file_reports_bad_url_line(monkeypatch, tmp_path):
    isolate_playlists(monkeypatch, tmp_path)
    links = tmp_path / "links.txt"
    links.write_text("Bad | ftp://example.com/a.mp3", encoding="utf-8")

    with pytest.raises(playlist_store.PlaylistError, match="Dòng 1"):
        playlist_store.import_file("Demo", links, create_missing=True)
