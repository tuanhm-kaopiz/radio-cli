from __future__ import annotations

import threading
from typing import Any, Literal

from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Input, Static

from radio_cli import history, player, playlist_store, queue_store, search as search_module, stations
from radio_cli.search import SearchError
from radio_cli.ytdlp_util import is_youtube_url
from radio_cli.config import CATEGORIES
from radio_cli.mpv_ipc import MpvIpcError, adjust_volume, get_property, get_volume, seek_absolute, seek_relative, toggle_mute, toggle_pause

Pane = Literal["stations", "search", "queue", "playlists", "history"]
PANES: list[Pane] = ["stations", "search", "queue", "playlists", "history"]
PANE_TITLES: dict[Pane, str] = {
    "stations": "◆ Stations",
    "search": "⌕ YouTube Search",
    "queue": "≡ Queue",
    "playlists": "▤ Playlists",
    "history": "◷ History",
}
SOURCE_ICONS = {
    "station": "◆",
    "search": "⌕",
    "url": "↗",
    "youtube": "⌕",
    "playlist": "▤",
    "podcast": "◉",
    "story": "▣",
    "broadcast": "◌",
}


def _clip(value: str, limit: int = 74) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def _format_seconds(value: float | int | None) -> str:
    if value is None or value < 0:
        return "--:--"
    total = int(value)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _progress_bar(position: float | None, duration: float | None, *, width: int = 28) -> str:
    if not duration or duration <= 0 or position is None:
        return "─" * width
    ratio = max(0.0, min(1.0, position / duration))
    filled = int(round(ratio * width))
    return "━" * filled + "─" * (width - filled)


class RadioTuiApp(App[None]):
    """Fullscreen terminal player for radio-cli."""

    TITLE = "Radio CLI Premium Player"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab,l", "next_pane", "Pane →"),
        Binding("shift+tab,h", "previous_pane", "Pane ←"),
        Binding("up,k", "cursor_up", "Up"),
        Binding("down,j", "cursor_down", "Down"),
        Binding("enter", "play_selected", "Play"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "blur_search", "Cancel search"),
        Binding("a", "add_selected", "Add"),
        Binding("p", "add_to_playlist", "Playlist"),
        Binding("e", "rename_selected", "Rename"),
        Binding("d,x,delete,backspace", "delete_selected", "Delete"),
        Binding("n", "play_next", "Next"),
        Binding("[", "seek_backward", "Seek -10s"),
        Binding("]", "seek_forward", "Seek +10s"),
        Binding("0", "restart_track", "Restart"),
        Binding("m", "mute", "Mute"),
        Binding("space", "pause", "Pause"),
        Binding("s", "stop", "Stop"),
        Binding("+", "volume_up", "Vol+"),
        Binding("-", "volume_down", "Vol-"),
        Binding("r", "refresh", "Refresh"),
    ]

    CSS = """
    Screen {
        background: #101418;
    }

    #root {
        height: 100%;
        padding: 0 1;
    }

    #now {
        height: 7;
    }

    #search_input, #playlist_rename_input {
        height: 3;
    }

    #body {
        height: 1fr;
    }

    #top_row, #middle_row, #bottom_row {
        height: 1fr;
    }

    #stations, #search, #queue, #playlists, #history {
        width: 1fr;
        height: 100%;
        margin-right: 1;
    }

    #search, #playlists, #history {
        margin-right: 0;
    }

    #shortcuts {
        height: 6;
    }

    #message {
        height: 3;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.active_pane: Pane = "stations"
        self.cursors: dict[Pane, int] = {pane: 0 for pane in PANES}
        self.search_results: list[dict[str, Any]] = []
        self._searching = False
        self._message = "Sẵn sàng. Nhấn / để search YouTube."
        self._last_seen_pid: int | None = None
        self._stop_requested = False
        self._target_playlist_id: str | None = None
        self._renaming_playlist_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="root"):
            yield Static(id="now")
            yield Input(placeholder="/ search YouTube V-Pop, Enter để tìm", id="search_input", disabled=True)
            yield Input(placeholder="Đổi tên playlist, Enter để lưu", id="playlist_rename_input", disabled=True)
            with Vertical(id="body"):
                with Horizontal(id="top_row"):
                    yield Static(id="stations")
                    yield Static(id="search")
                with Horizontal(id="middle_row"):
                    yield Static(id="queue")
                    yield Static(id="playlists")
                with Horizontal(id="bottom_row"):
                    yield Static(id="history")
            yield Static(id="shortcuts")
            yield Static(id="message")

    def on_mount(self) -> None:
        self.set_interval(2.0, self.refresh_ui)
        self.refresh_ui()

    def _items_for_pane(self, pane: Pane) -> list[dict[str, Any]]:
        if pane == "stations":
            return stations.load_stations()
        if pane == "search":
            return self.search_results
        if pane == "queue":
            if self.active_pane == "playlists":
                playlist = self._selected_item("playlists")
                if playlist is not None:
                    loaded = playlist_store.get(playlist.get("id", "")) or playlist
                    return list(loaded.get("items", []))
            return queue_store.list_items()
        if pane == "playlists":
            return playlist_store.list_playlists()
        return history.list_entries()

    def _selected_item(self, pane: Pane | None = None) -> dict[str, Any] | None:
        pane = pane or self.active_pane
        items = self._items_for_pane(pane)
        if not items:
            return None
        index = max(0, min(self.cursors[pane], len(items) - 1))
        self.cursors[pane] = index
        return items[index]

    def _set_message(self, message: str) -> None:
        self._message = message
        self.refresh_ui()

    def _now_panel(self) -> Panel:
        state = player.get_playback_state()
        if state is None:
            body = Text("∅ Không có gì đang phát. Chọn bài YouTube rồi Enter để phát.", style="dim")
            return Panel(body, title="▶ Now Playing", border_style="yellow")

        status = "Đang phát"
        volume = "?"
        muted = False
        live_station = player.is_live_station(state)
        try:
            status = "Tạm dừng" if get_property("pause") else "Đang phát"
            volume = f"{get_volume():.0f}%"
            muted = bool(get_property("mute"))
        except (MpvIpcError, SystemExit, TypeError, ValueError):
            pass

        if live_station:
            elapsed = player.live_elapsed_seconds(state)
            progress = "─" * 28
            time_label = f"LIVE · {_format_seconds(elapsed)}"
        else:
            position: float | None = None
            duration: float | None = None
            try:
                raw_position = get_property("time-pos")
                raw_duration = get_property("duration")
                position = float(raw_position) if raw_position is not None else None
                duration = float(raw_duration) if raw_duration is not None else None
            except (MpvIpcError, SystemExit, TypeError, ValueError):
                pass
            progress = _progress_bar(position, duration)
            time_label = f"{_format_seconds(position)} / {_format_seconds(duration)}"

        source_icon = SOURCE_ICONS.get(state.source, "•")
        source_label = {"search": "YouTube", "podcast": "Podcast", "story": "Story", "broadcast": "Broadcast"}.get(state.source, state.source)
        mute_label = "Muted" if muted else "Audio"
        body = (
            f"[bold cyan]{source_icon} {_clip(state.title, 96)}[/bold cyan]\n"
            f"{progress}  [bold]{time_label}[/bold]\n"
            f"Nguồn: {source_label} | PID: {state.pid} | {status} | {mute_label} | Volume: {volume}\n"
            f"[dim]{_clip(state.url, 110)}[/dim]"
        )
        return Panel(body, title="▶ Now Playing", border_style="green")

    def _shortcut_panel(self) -> Panel:
        body = (
            "[bold]Điều hướng[/bold]: Tab/l phải  |  Shift+Tab/h trái  |  ↑/↓ hoặc k/j di chuyển  |  / search  |  Esc hủy search\n"
            "[bold]Player[/bold]: Enter phát nền  |  Space pause/resume  |  n next  |  seek -10/+10  |  0 replay  |  m mute\n"
            "[bold]Queue/Playlist[/bold]: a thêm queue  |  p lưu vào playlist đang chọn  |  e đổi tên playlist  |  d/x/Delete xóa queue/history/playlist  |  [bold]Khác[/bold]: r refresh  |  q thoát"
        )
        return Panel(body, title="⌘ Shortcuts", border_style="magenta")

    def _list_panel(self, pane: Pane, title: str, items: list[dict[str, Any]]) -> Panel:
        lines: list[str] = []
        active = pane == self.active_pane
        selected = self.cursors[pane]

        if pane == "search" and self._searching:
            lines.append("[yellow]⌕ Đang tìm YouTube...[/yellow]")
        elif not items:
            lines.append("[dim]∅ Trống[/dim]")

        for index, item in enumerate(items[:8]):
            cursor = ">" if active and index == selected else " "
            if pane == "stations":
                cat = CATEGORIES.get(item.get("category", ""), item.get("category", ""))
                label = f"◆ {item.get('name', '—')} · {cat}"
            elif pane == "search":
                label = f"⌕ {item.get('title', '—')} · {item.get('duration', '--:--')}"
            elif pane == "playlists":
                label = f"▤ {item.get('name', '—')} · {len(item.get('items', []))} bài"
            else:
                source = item.get("source", "url")
                icon = SOURCE_ICONS.get(source, "•")
                label = f"{icon} {item.get('title', '—')} · {source}"
            style = "bold reverse" if active and index == selected else ""
            row = f"{cursor} {index + 1:02d}. {_clip(label, 54)}"
            lines.append(f"[{style}]{row}[/{style}]" if style else row)
        if len(items) > 8:
            lines.append(f"[dim]… +{len(items) - 8} mục nữa[/dim]")

        border = "cyan" if active else "blue"
        return Panel("\n".join(lines), title=title, border_style=border)

    def _maybe_autoplay_next(self) -> None:
        state = player.get_playback_state()
        if state is not None:
            self._last_seen_pid = state.pid
            self._stop_requested = False
            return
        if self._last_seen_pid is None or self._stop_requested:
            return

        self._last_seen_pid = None
        next_item = queue_store.pop_next()
        if next_item is None:
            self._set_message("Bài đã kết thúc. Queue trống.")
            return
        self._play_item(next_item, subtitle="Autoplay")

    def refresh_ui(self) -> None:
        self._maybe_autoplay_next()
        self.query_one("#now", Static).update(self._now_panel())
        self.query_one("#stations", Static).update(
            self._list_panel("stations", PANE_TITLES["stations"], self._items_for_pane("stations"))
        )
        self.query_one("#search", Static).update(
            self._list_panel("search", PANE_TITLES["search"], self._items_for_pane("search"))
        )
        queue_items = self._items_for_pane("queue")
        queue_title = PANE_TITLES["queue"]
        if self.active_pane == "playlists":
            playlist = self._selected_item("playlists")
            if playlist is not None:
                queue_title = f"▤ {playlist.get('name', '—')} · {len(queue_items)} bài"
        self.query_one("#queue", Static).update(self._list_panel("queue", queue_title, queue_items))
        self.query_one("#playlists", Static).update(
            self._list_panel("playlists", PANE_TITLES["playlists"], self._items_for_pane("playlists"))
        )
        self.query_one("#history", Static).update(
            self._list_panel("history", PANE_TITLES["history"], self._items_for_pane("history"))
        )
        self.query_one("#message", Static).update(Panel(self._message, title="● Status", border_style="yellow"))
        self.query_one("#shortcuts", Static).update(self._shortcut_panel())

    def action_next_pane(self) -> None:
        self.active_pane = PANES[(PANES.index(self.active_pane) + 1) % len(PANES)]
        self._sync_target_playlist()
        self.refresh_ui()

    def action_previous_pane(self) -> None:
        self.active_pane = PANES[(PANES.index(self.active_pane) - 1) % len(PANES)]
        self._sync_target_playlist()
        self.refresh_ui()

    def action_cursor_up(self) -> None:
        self.cursors[self.active_pane] = max(0, self.cursors[self.active_pane] - 1)
        self._sync_target_playlist()
        self.refresh_ui()

    def action_cursor_down(self) -> None:
        count = len(self._items_for_pane(self.active_pane))
        if count:
            self.cursors[self.active_pane] = min(count - 1, self.cursors[self.active_pane] + 1)
        self._sync_target_playlist()
        self.refresh_ui()

    def _sync_target_playlist(self) -> None:
        if self.active_pane != "playlists":
            return
        playlist = self._selected_item("playlists")
        if playlist is not None:
            self._target_playlist_id = str(playlist.get("id", "")) or None

    def action_focus_search(self) -> None:
        search_input = self.query_one("#search_input", Input)
        search_input.disabled = False
        search_input.value = ""
        search_input.focus()
        self._set_message("Nhập từ khóa V-Pop rồi Enter để tìm.")

    def action_blur_search(self) -> None:
        search_input = self.query_one("#search_input", Input)
        if not search_input.disabled:
            search_input.value = ""
            search_input.blur()
            search_input.disabled = True
            self._set_message("Đã hủy search.")
            return
        self._blur_rename_input()

    def _blur_rename_input(self) -> None:
        rename_input = self.query_one("#playlist_rename_input", Input)
        if rename_input.disabled:
            return
        rename_input.value = ""
        rename_input.blur()
        rename_input.disabled = True
        self._renaming_playlist_id = None
        self._set_message("Đã hủy đổi tên playlist.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search_input":
            query = event.value.strip()
            event.input.value = ""
            event.input.blur()
            event.input.disabled = True
            if not query:
                self._set_message("Search rỗng.")
                return
            self._start_search(query)
            return
        if event.input.id == "playlist_rename_input":
            new_name = event.value.strip()
            event.input.value = ""
            event.input.blur()
            event.input.disabled = True
            playlist_id = self._renaming_playlist_id
            self._renaming_playlist_id = None
            if not playlist_id:
                self._set_message("Không có playlist để đổi tên.")
                return
            if not new_name:
                self._set_message("Tên playlist không được rỗng.")
                return
            try:
                playlist = playlist_store.rename(playlist_id, new_name)
            except Exception as exc:
                self._set_message(str(exc) or "Không đổi tên được playlist.")
                return
            self._target_playlist_id = playlist.get("id")
            self._set_message(f"Đã đổi tên playlist: {playlist['name']}")

    def _start_search(self, query: str) -> None:
        if self._searching:
            self._set_message("Đang có search chạy, đợi hoàn tất.")
            return
        self._searching = True
        self.search_results = []
        self.active_pane = "search"
        self.cursors["search"] = 0
        self._set_message(f"Đang tìm YouTube: {query}")
        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query: str) -> None:
        try:
            results = search_module.search_vpop(query, limit=8, quiet=True)
            items = [
                {
                    "title": result.title,
                    "url": result.url,
                    "source": "search",
                    "video_id": result.video_id,
                    "duration": result.duration,
                }
                for result in results
            ]
        except (SearchError, Exception, SystemExit) as exc:
            self.call_from_thread(self._finish_search, query, [], str(exc) or "Search thất bại")
            return
        self.call_from_thread(self._finish_search, query, items, None)

    def _finish_search(self, query: str, items: list[dict[str, Any]], error: str | None) -> None:
        self._searching = False
        self.search_results = items
        self.active_pane = "search"
        self.cursors["search"] = 0
        if error:
            self._set_message(f"Search lỗi: {error}")
        elif items:
            self._set_message(f"Tìm thấy {len(items)} kết quả cho: {query}")
        else:
            self._set_message(f"Không có kết quả cho: {query}")

    def _play_item(self, item: dict[str, Any], *, subtitle: str) -> None:
        url = item.get("url", "")
        if is_youtube_url(url):
            self._set_message(f"Đang lấy stream YouTube: {_clip(item.get('title', '—'), 50)}")
            threading.Thread(
                target=self._play_item_worker,
                args=(item, subtitle),
                daemon=True,
            ).start()
            return
        try:
            title = self._start_playback(item)
        except (SystemExit, Exception) as exc:
            detail = str(exc) if str(exc) else "Không phát được mục này."
            self._set_message(f"Lỗi phát: {detail}")
            return
        self._on_playback_started(subtitle, title)

    def _play_item_worker(self, item: dict[str, Any], subtitle: str) -> None:
        try:
            title = self._start_playback(item)
        except (SystemExit, Exception) as exc:
            detail = str(exc) if str(exc) else "Không phát được mục này."
            self.call_from_thread(self._set_message, f"Lỗi phát: {detail}")
            return
        self.call_from_thread(self._on_playback_started, subtitle, title)

    def _start_playback(self, item: dict[str, Any]) -> str:
        if item.get("source") == "station" and item.get("station_id"):
            station = stations.station_by_id(item["station_id"])
            if station:
                player.play(
                    station["url"],
                    title=station["name"],
                    source="station",
                    station_id=station["id"],
                    background=True,
                    quiet=True,
                )
                return station["name"]
        player.play(
            item["url"],
            title=item["title"],
            source=item.get("source", "url"),
            station_id=item.get("station_id"),
            background=True,
            quiet=True,
        )
        return item["title"]

    def _on_playback_started(self, subtitle: str, title: str) -> None:
        self._stop_requested = False
        self._set_message(f"{subtitle}: {title}")

    def _play_playlist(self, playlist: dict[str, Any], *, shuffle_items: bool = False) -> None:
        loaded = playlist_store.get(playlist.get("id", "")) or playlist
        items = list(loaded.get("items", []))
        if not items:
            self._set_message(f"Playlist trống: {loaded.get('name', '—')}")
            return
        if shuffle_items:
            import random

            random.shuffle(items)
        for item in items[1:]:
            queue_store.add_item(
                queue_store.make_item(title=item["title"], url=item["url"], source=item.get("source", "url")),
                allow_duplicate=False,
            )
        self._play_item(items[0], subtitle=f"Playlist · {loaded.get('name', '—')}")

    def _selected_playlist_item(self) -> dict[str, Any] | None:
        if self.active_pane == "stations":
            station = self._selected_item("stations")
            if station is None:
                return None
            return {"title": station["name"], "url": station["url"], "source": "station"}
        selected = self._selected_item()
        if selected is None or "url" not in selected:
            return None
        return {"title": selected.get("title", selected.get("url", "")), "url": selected["url"], "source": selected.get("source", "url")}

    def action_play_selected(self) -> None:
        item = self._selected_item()
        if item is None:
            self._set_message("Không có mục nào để phát.")
            return

        if self.active_pane == "stations":
            self._play_item(
                {
                    "url": item["url"],
                    "title": item["name"],
                    "source": "station",
                    "station_id": item["id"],
                },
                subtitle="Đang phát",
            )
            return

        if self.active_pane == "queue":
            index = self.cursors["queue"] + 1
            queue_item = queue_store.remove(index)
            if queue_item is None:
                self._set_message("Mục queue không còn tồn tại.")
                return
            self._play_item(queue_item, subtitle="Đang phát từ queue")
            return

        if self.active_pane == "playlists":
            self._play_playlist(item)
            return

        self._play_item(item, subtitle="Đang phát")

    def action_add_selected(self) -> None:
        if self.active_pane == "stations":
            station = self._selected_item("stations")
            if station is None:
                self._set_message("Không có station để thêm.")
                return
            item = queue_store.item_from_station(station)
        elif self.active_pane == "search":
            selected = self._selected_item("search")
            if selected is None:
                self._set_message("Không có kết quả search để thêm.")
                return
            item = queue_store.make_item(title=selected["title"], url=selected["url"], source="search")
        else:
            self._set_message("Phím a chỉ thêm từ Stations hoặc YouTube Search vào queue.")
            return

        if queue_store.has_url(item["url"]):
            self._set_message(f"Đã có trong queue: {item['title']}")
            return
        total = queue_store.add_item(item)
        self._set_message(f"Đã thêm queue: {item['title']} ({total} mục)")

    def action_add_to_playlist(self) -> None:
        if self.active_pane == "playlists":
            self._set_message("Chọn station/search/queue/history rồi nhấn p để lưu vào playlist đang chọn. Enter để phát playlist.")
            return

        item = self._selected_playlist_item()
        if item is None:
            self._set_message("Chọn station, search, queue hoặc history để lưu playlist.")
            return
        target = self._target_playlist_id or "Danh sách yêu thích 1"
        try:
            playlist, added = playlist_store.add_item(
                target,
                playlist_store.make_item(title=item["title"], url=item["url"]),
                create_missing=True,
            )
        except Exception as exc:
            self._set_message(str(exc) or "Không lưu được playlist.")
            return
        self._target_playlist_id = playlist.get("id")
        action = "Đã lưu" if added else "Đã có"
        self._set_message(f"{action} trong {playlist['name']}: {item['title']}")

    def action_rename_selected(self) -> None:
        if self.active_pane != "playlists":
            self._set_message("Phím e chỉ đổi tên khi đang ở panel Playlists.")
            return
        playlist = self._selected_item("playlists")
        if playlist is None:
            self._set_message("Không có playlist để đổi tên.")
            return
        rename_input = self.query_one("#playlist_rename_input", Input)
        rename_input.disabled = False
        rename_input.value = playlist.get("name", "")
        rename_input.focus()
        self._renaming_playlist_id = str(playlist.get("id", ""))
        self._set_message("Nhập tên mới rồi Enter. Esc để hủy.")

    def action_delete_selected(self) -> None:
        if self.active_pane == "queue":
            items = queue_store.list_items()
            if not items:
                self._set_message("Queue trống.")
                return

            index = max(0, min(self.cursors["queue"], len(items) - 1))
            removed = queue_store.remove(index + 1)
            if removed is None:
                self._set_message("Mục queue không còn tồn tại.")
                return

            remaining = queue_store.list_items()
            self.cursors["queue"] = max(0, min(index, len(remaining) - 1)) if remaining else 0
            self._set_message(f"Đã xóa khỏi queue: {removed['title']}")
            return

        if self.active_pane == "history":
            items = history.list_entries()
            if not items:
                self._set_message("History trống.")
                return

            index = max(0, min(self.cursors["history"], len(items) - 1))
            removed = history.remove(index + 1)
            if removed is None:
                self._set_message("Mục history không còn tồn tại.")
                return

            remaining = history.list_entries()
            self.cursors["history"] = max(0, min(index, len(remaining) - 1)) if remaining else 0
            self._set_message(f"Đã xóa khỏi history: {removed['title']}")
            return

        if self.active_pane == "playlists":
            playlists = playlist_store.list_playlists()
            if not playlists:
                self._set_message("Chưa có playlist.")
                return

            index = max(0, min(self.cursors["playlists"], len(playlists) - 1))
            playlist = playlists[index]
            removed = playlist_store.delete(playlist.get("id", playlist.get("name", "")))
            if removed is None:
                self._set_message("Playlist không còn tồn tại.")
                return

            remaining = playlist_store.list_playlists()
            self.cursors["playlists"] = max(0, min(index, len(remaining) - 1)) if remaining else 0
            if self._target_playlist_id == removed.get("id"):
                self._target_playlist_id = None
            self._sync_target_playlist()
            self._set_message(f"Đã xóa playlist: {removed['name']}")
            return

        self._set_message("Phím d/x/Delete chỉ xóa mục khi đang ở panel Queue, History hoặc Playlists.")

    def action_play_next(self) -> None:
        item = queue_store.pop_next()
        if item is None:
            self._set_message("Queue trống.")
            return
        self._play_item(item, subtitle="Next")

    def action_pause(self) -> None:
        try:
            paused = toggle_pause()
        except (MpvIpcError, SystemExit) as exc:
            self._set_message(str(exc) or "Không pause được.")
            return
        self._set_message("Đã tạm dừng." if paused else "Đang phát tiếp.")

    def action_stop(self) -> None:
        self._stop_requested = True
        self._last_seen_pid = None
        if player.stop():
            self._set_message("Đã dừng player.")
        else:
            self._set_message("Không có gì đang phát.")

    def action_volume_up(self) -> None:
        self._adjust_volume(5)

    def action_volume_down(self) -> None:
        self._adjust_volume(-5)

    def action_seek_backward(self) -> None:
        self._seek(-10)

    def action_seek_forward(self) -> None:
        self._seek(10)

    def action_restart_track(self) -> None:
        try:
            seek_absolute(0)
        except (MpvIpcError, SystemExit) as exc:
            self._set_message(str(exc) or "Không restart được.")
            return
        self._set_message("Đã phát lại từ đầu.")

    def action_mute(self) -> None:
        try:
            muted = toggle_mute()
        except (MpvIpcError, SystemExit) as exc:
            self._set_message(str(exc) or "Không mute được.")
            return
        self._set_message("Đã mute." if muted else "Đã bật âm thanh.")

    def _seek(self, seconds: float) -> None:
        try:
            seek_relative(seconds)
        except (MpvIpcError, SystemExit) as exc:
            self._set_message(str(exc) or "Không tua được.")
            return
        direction = "tới" if seconds > 0 else "lùi"
        self._set_message(f"Đã tua {direction} {abs(int(seconds))}s.")

    def _adjust_volume(self, delta: float) -> None:
        try:
            volume = adjust_volume(delta)
        except (MpvIpcError, SystemExit) as exc:
            self._set_message(str(exc) or "Không chỉnh volume được.")
            return
        self._set_message(f"Volume: {volume:.0f}%")

    def action_refresh(self) -> None:
        self._set_message("Đã refresh.")


def run_tui() -> None:
    RadioTuiApp().run()
