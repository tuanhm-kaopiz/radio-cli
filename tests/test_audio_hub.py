from __future__ import annotations

from radio_cli import audio_hub


def isolate_hub(monkeypatch, tmp_path):
    monkeypatch.setattr(audio_hub, "AUDIO_HUB_FILE", tmp_path / "audio_hub.json")
    monkeypatch.setattr(audio_hub, "ensure_dirs", lambda: None)


def test_add_list_and_remove_feed(monkeypatch, tmp_path):
    isolate_hub(monkeypatch, tmp_path)

    feed = audio_hub.add_feed(name="Demo Podcast", rss_url="https://example.com/rss", kind="podcast")
    same = audio_hub.add_feed(name="Demo Podcast", rss_url="https://example.com/rss", kind="podcast")

    assert feed["id"] == "demo-podcast"
    assert same["id"] == feed["id"]
    assert len(audio_hub.list_feeds()) == 1
    assert audio_hub.get_feed("demo-podcast") is not None
    assert audio_hub.remove_feed("demo-podcast")["name"] == "Demo Podcast"
    assert audio_hub.list_feeds() == []


def test_fetch_episodes_from_rss(monkeypatch, tmp_path):
    isolate_hub(monkeypatch, tmp_path)
    rss = b'<?xml version="1.0"?>\n<rss version="2.0">\n  <channel>\n    <title>Demo</title>\n    <item>\n      <title>Episode One</title>\n      <pubDate>Thu, 11 Jun 2026 00:00:00 GMT</pubDate>\n      <enclosure url="https://example.com/one.mp3" type="audio/mpeg" />\n    </item>\n    <item>\n      <title>Episode Two</title>\n      <link>https://example.com/two.mp3</link>\n    </item>\n  </channel>\n</rss>'

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return rss

    monkeypatch.setattr(audio_hub.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    feed = audio_hub.add_feed(name="Stories", rss_url="https://example.com/rss", kind="story")

    episodes = audio_hub.fetch_episodes(feed, limit=5)

    assert [episode["title"] for episode in episodes] == ["Episode One", "Episode Two"]
    assert episodes[0]["url"] == "https://example.com/one.mp3"
    assert episodes[0]["source"] == "story"
    assert audio_hub.get_episode("stories", 2)["title"] == "Episode Two"
