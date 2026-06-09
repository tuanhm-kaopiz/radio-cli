from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table

from radio_cli.config import CATEGORIES
from radio_cli.search import SearchResult

console = Console()


def show_station_table(stations: list[dict[str, Any]], *, favorite_ids: set[str] | None = None) -> None:
    favs = favorite_ids or set()
    table = Table(title="📻 Danh sách kênh radio Việt Nam", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("", width=2)
    table.add_column("ID", style="cyan", width=14)
    table.add_column("Tên kênh", style="bold", min_width=18)
    table.add_column("Meta", width=24)

    for i, station in enumerate(stations, 1):
        star = "★" if station["id"] in favs else ""
        cat = CATEGORIES.get(station["category"], station["category"])
        tags = ", ".join(station.get("tags", [])[:3])
        meta_parts = [station["frequency"], cat]
        if tags:
            meta_parts.append(tags)
        table.add_row(str(i), star, station["id"], station["name"], " · ".join(meta_parts))

    console.print(table)


def show_search_table(results: list[SearchResult]) -> None:
    table = Table(title="🎵 Kết quả tìm kiếm V-Pop", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Bài hát", style="bold")
    table.add_column("Thời lượng", width=10)

    for i, item in enumerate(results, 1):
        table.add_row(str(i), item.title, item.duration)

    console.print(table)


def show_playback_panel(
    title: str,
    *,
    subtitle: str = "",
    frequency: str = "",
    category: str = "",
    background: bool = False,
) -> None:
    mode = "nền" if background else "trực tiếp"
    lines = [f"[bold cyan]{title}[/bold cyan]"]
    if subtitle:
        lines.append(f"[dim]{subtitle}[/dim]")
    meta = []
    if frequency:
        meta.append(f"Tần số: {frequency}")
    if category:
        meta.append(f"Thể loại: {category}")
    if meta:
        lines.append("  |  ".join(meta))
    lines.append("")
    if background:
        lines.append("[yellow]Đang phát nền.[/yellow] Dùng [bold]radio stop[/bold] để dừng.")
    else:
        lines.append("[yellow]Đang phát...[/yellow] Nhấn Ctrl+C để dừng.")

    console.print(
        Panel("\n".join(lines), title=f"📻 Radio Việt Nam ({mode})", border_style="green")
    )


def show_history_table(entries: list[dict[str, Any]]) -> None:
    table = Table(title="🕐 Lịch sử nghe gần đây", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Tên", style="bold")
    table.add_column("Nguồn", width=10)
    table.add_column("Thời gian", width=16)

    source_labels = {"station": "Radio", "search": "V-Pop", "url": "URL"}
    for i, entry in enumerate(entries, 1):
        played = entry.get("played_at")
        if played:
            when = datetime.fromtimestamp(played).strftime("%d/%m %H:%M")
        else:
            when = "—"
        src = source_labels.get(entry.get("source", ""), entry.get("source", ""))
        table.add_row(str(i), entry.get("title", "—"), src, when)

    console.print(table)


def show_fav_tracks_table(tracks: list[dict[str, str]]) -> None:
    table = Table(title="★ Bài hát yêu thích", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Bài hát", style="bold")
    for i, track in enumerate(tracks, 1):
        table.add_row(str(i), track.get("title", "—"))
    console.print(table)


def pick_from_list(count: int, prompt: str = "Chọn số") -> int:
    try:
        return IntPrompt.ask(
            f"\n{prompt}",
            choices=[str(i) for i in range(1, count + 1)],
            show_choices=False,
        )
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Thoát.[/dim]")
        raise SystemExit(0) from None


def show_queue_table(items: list[dict[str, Any]]) -> None:
    table = Table(title="▶ Queue", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Tên", style="bold")
    table.add_column("Nguồn", width=10)

    source_labels = {"station": "Radio", "search": "V-Pop", "url": "URL"}
    for i, item in enumerate(items, 1):
        source = source_labels.get(item.get("source", ""), item.get("source", ""))
        table.add_row(str(i), item.get("title", "—"), source)

    console.print(table)


def queue_summary(items: list[dict[str, Any]], limit: int = 6) -> Table:
    table = Table(title="Queue", show_header=True, expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Tên", style="bold")
    table.add_column("Nguồn", width=10)
    for i, item in enumerate(items[:limit], 1):
        table.add_row(str(i), item.get("title", "—"), item.get("source", "—"))
    if len(items) > limit:
        table.add_row("…", f"+{len(items) - limit} mục nữa", "")
    return table


def history_summary(entries: list[dict[str, Any]], limit: int = 6) -> Table:
    table = Table(title="Gần đây", show_header=True, expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Tên", style="bold")
    table.add_column("Thời gian", width=12)
    for i, entry in enumerate(entries[:limit], 1):
        played = entry.get("played_at")
        when = datetime.fromtimestamp(played).strftime("%H:%M") if played else "—"
        table.add_row(str(i), entry.get("title", "—"), when)
    return table
