from __future__ import annotations

from radio_cli import queue_store


def isolate_queue(monkeypatch, tmp_path):
    monkeypatch.setattr(queue_store, "QUEUE_FILE", tmp_path / "queue.json")
    monkeypatch.setattr(queue_store, "ensure_dirs", lambda: None)


def test_add_list_and_pop_queue_items(monkeypatch, tmp_path):
    isolate_queue(monkeypatch, tmp_path)

    first = queue_store.make_item(title="One", url="https://example.com/1")
    second = queue_store.make_item(title="Two", url="https://example.com/2", source="station", station_id="two")

    assert queue_store.add_item(first) == 1
    assert queue_store.add_item(second) == 2
    assert [item["title"] for item in queue_store.list_items()] == ["One", "Two"]

    popped = queue_store.pop_next()

    assert popped is not None
    assert popped["title"] == "One"
    assert [item["title"] for item in queue_store.list_items()] == ["Two"]


def test_remove_and_clear_queue_items(monkeypatch, tmp_path):
    isolate_queue(monkeypatch, tmp_path)
    queue_store.add_many([
        queue_store.make_item(title="One", url="https://example.com/1"),
        queue_store.make_item(title="Two", url="https://example.com/2"),
    ])

    removed = queue_store.remove(2)

    assert removed is not None
    assert removed["title"] == "Two"
    assert queue_store.clear() == 1
    assert queue_store.list_items() == []


def test_item_from_target_rejects_invalid_url_scheme(monkeypatch, tmp_path):
    isolate_queue(monkeypatch, tmp_path)

    assert queue_store.item_from_target("ftp://example.com/radio.mp3") is None


def test_invalid_indexes_return_none(monkeypatch, tmp_path):
    isolate_queue(monkeypatch, tmp_path)

    assert queue_store.get_item(1) is None
    assert queue_store.remove(1) is None
    assert queue_store.pop_next() is None


def test_add_item_skips_duplicate_urls_by_default(monkeypatch, tmp_path):
    isolate_queue(monkeypatch, tmp_path)
    item = queue_store.make_item(title="One", url="https://example.com/1")

    assert queue_store.add_item(item) == 1
    assert queue_store.add_item(item) == 1
    assert len(queue_store.list_items()) == 1
    assert queue_store.has_url("https://example.com/1") is True


def test_add_many_skips_existing_and_batch_duplicates(monkeypatch, tmp_path):
    isolate_queue(monkeypatch, tmp_path)
    queue_store.add_item(queue_store.make_item(title="One", url="https://example.com/1"))

    total = queue_store.add_many([
        queue_store.make_item(title="One again", url="https://example.com/1"),
        queue_store.make_item(title="Two", url="https://example.com/2"),
        queue_store.make_item(title="Two again", url="https://example.com/2"),
    ])

    assert total == 2
    assert [item["title"] for item in queue_store.list_items()] == ["One", "Two"]
