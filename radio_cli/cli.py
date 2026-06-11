from __future__ import annotations

import random
from pathlib import Path
import time
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from radio_cli import audio_hub, data_io, display, favorites, history, player, playlist_store, premium, queue_store, search, stations
from radio_cli.config import CATEGORIES
from radio_cli.logging_config import setup_logging
from radio_cli.station_validation import validate_stations_data
from radio_cli.player import PlayerError
from radio_cli.url_utils import UrlValidationError, validate_http_url
from radio_cli.mpv_ipc import (
    MpvIpcError,
    adjust_volume,
    get_property,
    get_volume,
    parse_volume_delta,
    set_volume,
    toggle_pause,
)

app = typer.Typer(
    name="radio",
    help="Nghe radio Việt Nam & V-Pop trên terminal (Linux / macOS / Windows).",
    no_args_is_help=False,
)
fav_app = typer.Typer(help="Quản lý kênh yêu thích.")
history_app = typer.Typer(help="Lịch sử nghe gần đây.")
queue_app = typer.Typer(help="Quản lý queue phát nhạc/radio.")
playlist_app = typer.Typer(help="Quản lý playlist cá nhân.")
hub_app = typer.Typer(help="Audio Hub: podcast, truyện, broadcast RSS.")
app.add_typer(fav_app, name="fav")
app.add_typer(history_app, name="history")
app.add_typer(queue_app, name="queue")
app.add_typer(playlist_app, name="playlist")
app.add_typer(hub_app, name="hub")

console = Console()


def _run_player_or_exit(*args: Any, **kwargs: Any) -> None:
    try:
        player.play(*args, **kwargs)
    except PlayerError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


def _play_station(station: dict[str, Any], *, background: bool) -> None:
    category = CATEGORIES.get(station["category"], station["category"])
    display.show_playback_panel(
        station["name"],
        subtitle=station["description"],
        frequency=station["frequency"],
        category=category,
        background=background,
    )
    _run_player_or_exit(
        station["url"],
        title=station["name"],
        source="station",
        station_id=station["id"],
        background=background,
        fallback_urls=stations.stream_urls(station)[1:],
    )


def _play_history_entry(entry: dict[str, Any], *, background: bool, subtitle: str = "Lịch sử") -> None:
    title = entry["title"]
    url = entry["url"]
    source = entry.get("source", "url")
    station_id = entry.get("station_id")

    if source == "station" and station_id:
        station = stations.station_by_id(station_id)
        if station:
            _play_station(station, background=background)
            return

    display.show_playback_panel(title, subtitle=subtitle, background=background)
    _run_player_or_exit(
        url,
        title=title,
        source=source,
        station_id=station_id,
        background=background,
        quiet=not background,
    )


def _play_queue_item(item: dict[str, Any], *, background: bool, subtitle: str = "Queue") -> None:
    if item.get("source") == "station" and item.get("station_id"):
        station = stations.station_by_id(item["station_id"])
        if station:
            _play_station(station, background=background)
            return

    display.show_playback_panel(item["title"], subtitle=subtitle, background=background)
    _run_player_or_exit(
        item["url"],
        title=item["title"],
        source=item.get("source", "url"),
        station_id=item.get("station_id"),
        background=background,
        quiet=not background,
    )



def _playlist_or_exit(name_or_id: str) -> dict[str, Any]:
    playlist = playlist_store.get(name_or_id)
    if playlist is None:
        console.print(f"[red]Không tìm thấy playlist:[/red] {name_or_id}")
        raise typer.Exit(1)
    return playlist


def _show_playlist_table(items: list[dict[str, Any]], *, title: str) -> None:
    table = Table(title=title, show_lines=True)
    table.add_column("#", justify="right", width=4)
    table.add_column("Tên", style="bold")
    table.add_column("Nguồn", width=10)
    table.add_column("URL", overflow="fold")
    for index, item in enumerate(items, 1):
        table.add_row(str(index), item.get("title", ""), item.get("source", "url"), item.get("url", ""))
    console.print(table)


def _play_playlist_items(
    playlist: dict[str, Any],
    *,
    background: bool,
    shuffle_items: bool = False,
    replace_queue: bool = False,
) -> None:
    items = list(playlist.get("items", []))
    if not items:
        console.print(f"[yellow]Playlist trống:[/yellow] {playlist['name']}")
        raise typer.Exit(1)
    if shuffle_items:
        random.shuffle(items)
    if replace_queue:
        queue_store.clear()
    for item in items[1:]:
        queue_store.add_item(
            queue_store.make_item(title=item["title"], url=item["url"], source=item.get("source", "url")),
            allow_duplicate=False,
        )
    first = items[0]
    display.show_playback_panel(first["title"], subtitle=f"Playlist · {playlist['name']}", background=background)
    _run_player_or_exit(
        first["url"],
        title=first["title"],
        source=first.get("source", "playlist"),
        background=background,
        quiet=not background,
    )


def _dashboard_layout() -> Layout:
    state = player.get_playback_state()
    queue_items = queue_store.list_items()
    recent = history.list_entries()

    if state is None:
        now = "[dim]Không có gì đang phát.[/dim]"
    else:
        status = "Đang phát"
        volume = "?"
        try:
            status = "Tạm dừng" if get_property("pause") else "Đang phát"
            volume = f"{get_volume():.0f}%"
        except MpvIpcError:
            pass
        now = (
            f"[bold cyan]{state.title}[/bold cyan]\n"
            f"Nguồn: {state.source} | PID: {state.pid} | {status} | Volume: {volume}\n"
            f"[dim]{state.url}[/dim]"
        )

    layout = Layout()
    layout.split_column(
        Layout(Panel(now, title="Now Playing", border_style="green"), size=6),
        Layout(name="body"),
        Layout(Panel("radio queue add <id/url> | radio next --bg | radio pause | radio vol +10 | radio stop", title="Commands"), size=4),
    )
    layout["body"].split_row(
        Layout(display.queue_summary(queue_items), ratio=1),
        Layout(display.history_summary(recent), ratio=1),
    )
    return layout


@app.command("list")
def list_cmd(
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Lọc: nhac-tre, giai-tri, giao-thong, tag hoặc thành phố"),
    ] = None,
    favorites_only: Annotated[
        bool, typer.Option("--fav", "-f", help="Chỉ hiện kênh yêu thích")
    ] = False,
) -> None:
    """Hiển thị danh sách kênh radio."""
    all_stations = stations.load_stations()
    fav_ids = set(favorites.list_station_ids())

    if favorites_only:
        all_stations = [s for s in all_stations if s["id"] in fav_ids]
    else:
        all_stations = stations.filter_stations(all_stations, category)

    if not all_stations:
        console.print("[yellow]Không tìm thấy kênh nào.[/yellow]")
        raise typer.Exit(1)

    display.show_station_table(all_stations, favorite_ids=fav_ids)


@app.command("play")
def play_cmd(
    target: Annotated[str, typer.Argument(help="ID kênh, tên gần đúng, alias hoặc URL stream")],
    background: Annotated[
        bool, typer.Option("--bg", "-b", help="Phát nền, trả terminal ngay")
    ] = False,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Lọc khi tìm theo tên")
    ] = None,
) -> None:
    """Phát radio: `radio play vov3` hoặc `radio play vov3 --bg`."""
    if target.startswith(("http://", "https://")):
        try:
            stream_url = validate_http_url(target, field_name="URL stream")
        except UrlValidationError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        display.show_playback_panel(stream_url, subtitle="Stream trực tiếp", background=background)
        _run_player_or_exit(stream_url, title=stream_url, source="url", background=background)
        return

    if "://" in target:
        console.print("[red]URL stream phải dùng http hoặc https.[/red]")
        raise typer.Exit(1)

    filtered = stations.filter_stations(stations.load_stations(), category)
    found = stations.resolve_station(target, filtered)
    if not found:
        console.print(f"[red]Không tìm thấy hoặc chưa đủ rõ kênh:[/red] {target}")
        console.print("Dùng [bold]radio list[/bold] để xem danh sách hoặc thêm [bold]--category[/bold].")
        raise typer.Exit(1)

    _play_station(found, background=background)


@app.command("random")
def random_cmd(
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Lọc theo thể loại/tag/thành phố")
    ] = None,
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Chọn ngẫu nhiên một kênh phù hợp và phát."""
    candidates = stations.filter_stations(stations.load_stations(), category)
    if not candidates:
        console.print("[yellow]Không có kênh phù hợp để random.[/yellow]")
        raise typer.Exit(1)
    chosen = random.choice(candidates)
    console.print(f"[dim]Random:[/dim] [bold]{chosen['name']}[/bold]")
    _play_station(chosen, background=background)


@app.command("resume")
def resume_cmd(
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Phát lại mục gần nhất trong lịch sử."""
    entries = history.list_entries()
    if not entries:
        console.print("[yellow]Chưa có lịch sử để resume.[/yellow]")
        raise typer.Exit(1)
    _play_history_entry(entries[0], background=background, subtitle="Resume")


@app.command("sleep")
def sleep_cmd(
    duration: Annotated[str, typer.Argument(help="Thời gian dừng tự động, vd: 30, 30m, 1h, 90s")],
) -> None:
    """Hẹn giờ dừng player đang chạy."""
    state = player.get_playback_state()
    if state is None:
        console.print("[yellow]Không có gì đang phát để hẹn giờ.[/yellow]")
        raise typer.Exit(1)

    try:
        seconds = premium.parse_duration_seconds(duration)
    except ValueError:
        console.print(f"[red]Thời gian không hợp lệ:[/red] {duration}")
        console.print("Ví dụ: [bold]radio sleep 30m[/bold], [bold]radio sleep 1h[/bold], [bold]radio sleep 90s[/bold]")
        raise typer.Exit(1) from None

    console.print(
        f"[green]⏱[/green] Sẽ dừng [bold]{state.title}[/bold] sau "
        f"[bold]{premium.format_duration(seconds)}[/bold]. Nhấn Ctrl+C để hủy hẹn giờ."
    )
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        console.print("\n[dim]Đã hủy hẹn giờ. Player vẫn tiếp tục chạy.[/dim]")
        raise typer.Exit(0) from None

    if player.stop():
        console.print(f"[green]■[/green] Đã dừng sau {premium.format_duration(seconds)}.")
    else:
        console.print("[yellow]Player đã dừng trước khi hết giờ.[/yellow]")


@app.command("doctor")
def doctor_cmd(
    fix: Annotated[bool, typer.Option("--fix", help="Thử sửa các lỗi môi trường an toàn")] = False,
) -> None:
    """Kiểm tra môi trường, dependency và dữ liệu local."""
    if fix:
        fixes = premium.run_doctor_fixes()
        fix_table = Table(title="Radio CLI Doctor Fix", show_lines=True)
        fix_table.add_column("Fix", style="bold")
        fix_table.add_column("Status", width=8)
        fix_table.add_column("Detail")
        for item in fixes:
            status = "[green]OK[/green]" if item.ok else "[yellow]MANUAL[/yellow]"
            fix_table.add_row(item.name, status, item.detail)
        console.print(fix_table)

    checks = premium.run_doctor_checks()
    table = Table(title="Radio CLI Doctor", show_lines=True)
    table.add_column("Check", style="bold")
    table.add_column("Status", width=8)
    table.add_column("Detail")

    for check in checks:
        status = "[green]OK[/green]" if check.ok else "[red]FAIL[/red]"
        table.add_row(check.name, status, check.detail)

    console.print(table)
    if not all(check.ok for check in checks):
        raise typer.Exit(1)


@app.command("validate-stations")
def validate_stations_cmd() -> None:
    """Kiểm tra schema và URL trong danh sách kênh đóng gói."""
    issues = validate_stations_data()
    table = Table(title="Station Validation", show_lines=True)
    table.add_column("Level", width=8)
    table.add_column("Station", style="cyan")
    table.add_column("Message")
    for issue in issues:
        style = "red" if issue.level == "error" else "yellow"
        table.add_row(f"[{style}]{issue.level.upper()}[/{style}]", issue.station_id, issue.message)
    if issues:
        console.print(table)
    else:
        console.print("[green]OK[/green] Station data hợp lệ.")
    if any(issue.level == "error" for issue in issues):
        raise typer.Exit(1)


@app.command("export-data")
def export_data_cmd(
    path: Annotated[Path, typer.Argument(help="File JSON backup cần ghi")],
) -> None:
    """Export favorites, history, queue và Audio Hub ra JSON."""
    try:
        written = data_io.export_data(path)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]✓[/green] Đã export dữ liệu: [bold]{written}[/bold]")


@app.command("import-data")
def import_data_cmd(
    path: Annotated[Path, typer.Argument(help="File JSON backup cần import")],
    merge: Annotated[bool, typer.Option("--merge", help="Merge vào dữ liệu hiện có thay vì ghi đè từng nhóm")] = False,
) -> None:
    """Import favorites, history, queue và Audio Hub từ JSON."""
    try:
        imported = data_io.import_data(path, merge=merge)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    label = ", ".join(imported) if imported else "không có dữ liệu"
    console.print(f"[green]✓[/green] Đã import: {label}")


@app.command("stop")
def stop_cmd() -> None:
    """Dừng phát nhạc/radio đang chạy nền."""
    state = player.get_playback_state()
    if state is None:
        if player.stop():
            console.print("[dim]Đã dừng.[/dim]")
        else:
            console.print("[yellow]Không có gì đang phát.[/yellow]")
        return

    title = state.title
    if player.stop():
        console.print(f"[green]■[/green] Đã dừng: [bold]{title}[/bold]")
    else:
        console.print("[yellow]Không thể dừng player.[/yellow]")
        raise typer.Exit(1)


@app.command("status")
def status_cmd() -> None:
    """Xem trạng thái phát hiện tại."""
    state = player.get_playback_state()
    if state is None:
        console.print("[dim]Không có gì đang phát.[/dim]")
        return

    extra = ""
    try:
        paused = get_property("pause")
        vol = get_volume()
        pause_label = "Tạm dừng" if paused else "Đang phát"
        extra = f"\nTrạng thái: {pause_label}  |  Volume: {vol:.0f}%"
    except MpvIpcError:
        pass

    console.print(
        Panel(
            f"[bold cyan]{state.title}[/bold cyan]\n"
            f"Nguồn: {state.source}  |  PID: {state.pid}{extra}\n"
            f"[dim]{state.url}[/dim]",
            title="▶ Đang phát",
            border_style="green",
        )
    )


@app.command("pause")
def pause_cmd() -> None:
    """Tạm dừng / tiếp tục phát (toggle)."""
    try:
        paused = toggle_pause()
    except MpvIpcError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if paused:
        console.print("[yellow]⏸[/yellow] Đã tạm dừng.")
    else:
        console.print("[green]▶[/green] Đang phát tiếp.")


@app.command("vol")
def vol_cmd(
    level: Annotated[
        str,
        typer.Argument(help="Mức volume 0-100, hoặc +10 / -10"),
    ],
) -> None:
    """Điều chỉnh âm lượng player đang chạy."""
    try:
        delta = parse_volume_delta(level)
        if delta is not None:
            new_vol = adjust_volume(delta)
        else:
            try:
                target = float(level)
            except ValueError:
                console.print(f"[red]Volume không hợp lệ: {level}[/red]")
                console.print("Dùng: [bold]radio vol 70[/bold] hoặc [bold]radio vol +10[/bold]")
                raise typer.Exit(1) from None
            new_vol = set_volume(target)
    except MpvIpcError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    console.print(f"🔊 Volume: [bold]{new_vol:.0f}%[/bold]")


@app.command("search")
def search_cmd(
    query: Annotated[str, typer.Argument(help="Tên bài hát / ca sĩ V-Pop")],
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=50, help="Số kết quả")] = 10,
    pick: Annotated[
        int | None, typer.Option("--pick", "-p", help="Chọn kết quả theo số (1-N)")
    ] = None,
    play_first: Annotated[
        bool, typer.Option("--play", help="Phát kết quả đầu tiên ngay")
    ] = False,
    background: Annotated[
        bool, typer.Option("--bg", "-b", help="Phát nền")
    ] = False,
    save_fav: Annotated[
        bool, typer.Option("--fav", help="Lưu bài vào yêu thích sau khi chọn")
    ] = False,
) -> None:
    """Tìm & nghe V-Pop qua yt-dlp + mpv (Spotify CLI style)."""
    with console.status(f"[bold]Đang tìm:[/bold] {query}..."):
        results = search.search_vpop(query, limit=limit)

    if not results:
        console.print("[yellow]Không có kết quả.[/yellow]")
        raise typer.Exit(1)

    display.show_search_table(results)

    index = pick
    if play_first:
        index = 1
    elif index is None:
        index = display.pick_from_list(len(results), "Chọn bài để phát")

    if index < 1 or index > len(results):
        console.print(f"[red]Số lựa chọn không hợp lệ:[/red] {index}")
        raise typer.Exit(1)

    chosen = results[index - 1]
    display.show_playback_panel(chosen.title, subtitle="V-Pop · YouTube", background=background)

    if save_fav:
        favorites.add_track(chosen.title, chosen.url, chosen.video_id)
        console.print("[green]★[/green] Đã lưu vào yêu thích.")

    _run_player_or_exit(
        chosen.url,
        title=chosen.title,
        source="search",
        background=background,
        quiet=not background,
    )


@app.command("tui")
def tui_cmd() -> None:
    """Mở TUI player fullscreen."""
    try:
        from radio_cli.tui import run_tui
    except ImportError as exc:
        console.print("[red]Không tải được TUI.[/red] Cài dependency bằng: [bold]pip install -e .[/bold]")
        raise typer.Exit(1) from exc

    run_tui()


@app.command("dashboard")
def dashboard_cmd(
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Tự refresh dashboard")] = False,
    interval: Annotated[float, typer.Option("--interval", help="Số giây giữa mỗi lần refresh")] = 1.0,
) -> None:
    """Hiển thị dashboard player, queue và lịch sử."""
    if not watch:
        console.print(_dashboard_layout())
        return

    try:
        with Live(_dashboard_layout(), console=console, refresh_per_second=4, screen=False) as live:
            while True:
                time.sleep(max(0.2, interval))
                live.update(_dashboard_layout())
    except KeyboardInterrupt:
        raise typer.Exit(0) from None


@app.command("next")
def next_cmd(
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Phát mục tiếp theo trong queue."""
    item = queue_store.pop_next()
    if item is None:
        console.print("[yellow]Queue trống.[/yellow]")
        raise typer.Exit(1)
    _play_queue_item(item, background=background, subtitle="Queue · Next")


@queue_app.callback(invoke_without_command=True)
def queue_list(ctx: typer.Context) -> None:
    """Hiển thị queue hiện tại."""
    if ctx.invoked_subcommand is not None:
        return
    items = queue_store.list_items()
    if not items:
        console.print("[dim]Queue trống.[/dim]")
        console.print("Thêm bằng: [bold]radio queue add vov3[/bold]")
        return
    display.show_queue_table(items)


@queue_app.command("add")
def queue_add(
    targets: Annotated[list[str], typer.Argument(help="ID/tên kênh hoặc URL stream")],
) -> None:
    """Thêm một hoặc nhiều kênh/URL vào queue."""
    if not targets:
        console.print("[yellow]Chưa có mục nào để thêm.[/yellow]")
        raise typer.Exit(1)

    added = []
    skipped = []
    for target in targets:
        item = queue_store.item_from_target(target)
        if item is None:
            console.print(f"[red]Không tìm thấy:[/red] {target}")
            raise typer.Exit(1)
        if queue_store.has_url(item["url"]):
            skipped.append(item)
        else:
            added.append(item)

    total = queue_store.add_many(added)
    for item in added:
        console.print(f"[green]+[/green] {item['title']}")
    for item in skipped:
        console.print(f"[yellow]=[/yellow] Đã có trong queue: {item['title']}")
    console.print(f"[dim]Queue hiện có {total} mục.[/dim]")


@queue_app.command("play")
def queue_play(
    index: Annotated[int, typer.Option("--pick", "-p", help="Phát mục theo số; mặc định lấy mục đầu")] = 1,
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
    keep: Annotated[bool, typer.Option("--keep", help="Không xóa khỏi queue sau khi chọn")] = False,
) -> None:
    """Phát một mục trong queue."""
    item = queue_store.get_item(index) if keep else queue_store.remove(index)
    if item is None:
        console.print(f"[red]Không có mục số {index} trong queue.[/red]")
        raise typer.Exit(1)
    _play_queue_item(item, background=background)


@queue_app.command("next")
def queue_next(
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Alias của `radio next`."""
    next_cmd(background=background)


@queue_app.command("remove")
def queue_remove(
    index: Annotated[int, typer.Argument(help="Số thứ tự trong queue")],
) -> None:
    """Xóa một mục khỏi queue."""
    item = queue_store.remove(index)
    if item is None:
        console.print(f"[red]Không có mục số {index} trong queue.[/red]")
        raise typer.Exit(1)
    console.print(f"[dim]Đã xóa:[/dim] {item['title']}")


@queue_app.command("clear")
def queue_clear(
    force: Annotated[bool, typer.Option("--yes", "-y", help="Không hỏi xác nhận")] = False,
) -> None:
    """Xóa toàn bộ queue."""
    if not force and not typer.confirm("Xóa toàn bộ queue?"):
        raise typer.Exit(0)
    count = queue_store.clear()
    console.print(f"[dim]Đã xóa {count} mục.[/dim]")


@playlist_app.callback(invoke_without_command=True)
def playlist_list(ctx: typer.Context) -> None:
    """Hiển thị các playlist cá nhân."""
    if ctx.invoked_subcommand is not None:
        return
    playlists = playlist_store.list_playlists()
    if not playlists:
        console.print("[dim]Chưa có playlist.[/dim]")
        console.print('Tạo nhanh: [bold]radio playlist import "Danh sách yêu thích 1" links.txt --create[/bold]')
        return
    table = Table(title="Playlists", show_lines=True)
    table.add_column("#", justify="right", width=4)
    table.add_column("ID", style="cyan")
    table.add_column("Tên", style="bold")
    table.add_column("Số bài", justify="right")
    for index, playlist in enumerate(playlists, 1):
        table.add_row(str(index), playlist.get("id", ""), playlist.get("name", ""), str(len(playlist.get("items", []))))
    console.print(table)


@playlist_app.command("create")
def playlist_create(
    name: Annotated[str, typer.Argument(help="Tên playlist")],
) -> None:
    """Tạo playlist mới."""
    try:
        playlist = playlist_store.create(name)
    except playlist_store.PlaylistError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]+[/green] {playlist['name']} [dim]({playlist['id']})[/dim]")


@playlist_app.command("add")
def playlist_add(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist")],
    url: Annotated[str, typer.Argument(help="YouTube/stream URL")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="Tên hiển thị; mặc định là URL")] = None,
    create_missing: Annotated[bool, typer.Option("--create", help="Tự tạo playlist nếu chưa có")] = False,
) -> None:
    """Thêm một link vào playlist."""
    try:
        playlist, added = playlist_store.add_item(
            name,
            playlist_store.make_item(title=title or url, url=url),
            create_missing=create_missing,
        )
    except (playlist_store.PlaylistError, UrlValidationError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    marker = "[green]+[/green]" if added else "[yellow]=[/yellow]"
    status = "Đã thêm" if added else "Đã có"
    console.print(f"{marker} {status} trong [bold]{playlist['name']}[/bold].")


@playlist_app.command("import")
def playlist_import(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist")],
    path: Annotated[Path, typer.Argument(help="File .txt, mỗi dòng là URL hoặc Title | URL")],
    create_missing: Annotated[bool, typer.Option("--create", help="Tự tạo playlist nếu chưa có")] = False,
) -> None:
    """Import nhiều link vào playlist từ file text."""
    try:
        added, skipped = playlist_store.import_file(name, path, create_missing=create_missing)
    except playlist_store.PlaylistError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    playlist = _playlist_or_exit(name)
    console.print(f"[green]+[/green] {playlist['name']}: thêm {added}, bỏ qua trùng {skipped}.")


@playlist_app.command("show")
def playlist_show(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist")],
) -> None:
    """Xem nội dung playlist."""
    playlist = _playlist_or_exit(name)
    if not playlist.get("items"):
        console.print(f"[dim]Playlist trống:[/dim] {playlist['name']}")
        return
    _show_playlist_table(playlist["items"], title=f"Playlist · {playlist['name']}")


@playlist_app.command("play")
def playlist_play(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist")],
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
    replace_queue: Annotated[bool, typer.Option("--replace-queue", help="Xóa queue hiện tại trước khi nạp playlist")] = False,
) -> None:
    """Phát playlist: bài đầu phát ngay, các bài còn lại vào queue."""
    playlist = _playlist_or_exit(name)
    _play_playlist_items(playlist, background=background, replace_queue=replace_queue)


@playlist_app.command("shuffle")
def playlist_shuffle(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist")],
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
    replace_queue: Annotated[bool, typer.Option("--replace-queue", help="Xóa queue hiện tại trước khi nạp playlist")] = False,
) -> None:
    """Trộn playlist rồi phát."""
    playlist = _playlist_or_exit(name)
    _play_playlist_items(playlist, background=background, shuffle_items=True, replace_queue=replace_queue)


@playlist_app.command("remove")
def playlist_remove(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist")],
    index: Annotated[int, typer.Argument(help="Số thứ tự bài cần xóa")],
) -> None:
    """Xóa một bài khỏi playlist."""
    removed = playlist_store.remove_item(name, index)
    if removed is None:
        console.print(f"[red]Không xóa được mục số {index}.[/red]")
        raise typer.Exit(1)
    console.print(f"[dim]Đã xóa:[/dim] {removed['title']}")


@playlist_app.command("rename")
def playlist_rename(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist hiện tại")],
    new_name: Annotated[str, typer.Argument(help="Tên mới")],
) -> None:
    """Đổi tên playlist."""
    try:
        playlist = playlist_store.rename(name, new_name)
    except playlist_store.PlaylistError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]✓[/green] Đã đổi tên thành [bold]{playlist['name']}[/bold].")


@playlist_app.command("delete")
def playlist_delete(
    name: Annotated[str, typer.Argument(help="Tên hoặc ID playlist")],
    force: Annotated[bool, typer.Option("--yes", "-y", help="Không hỏi xác nhận")] = False,
) -> None:
    """Xóa toàn bộ playlist."""
    playlist = _playlist_or_exit(name)
    if not force and not typer.confirm(f"Xóa playlist {playlist['name']}?"):
        raise typer.Exit(0)
    removed = playlist_store.delete(name)
    if removed is None:
        console.print(f"[red]Không tìm thấy playlist:[/red] {name}")
        raise typer.Exit(1)
    console.print(f"[dim]Đã xóa playlist:[/dim] {removed['name']}")


@hub_app.command("add")
def hub_add(
    name: Annotated[str, typer.Argument(help="Tên podcast/truyện/broadcast")],
    rss_url: Annotated[str, typer.Argument(help="URL RSS feed")],
    kind: Annotated[str, typer.Option("--type", "-t", help="podcast, story hoặc broadcast")] = "podcast",
) -> None:
    """Thêm một RSS feed vào Audio Hub."""
    try:
        rss_url = validate_http_url(rss_url, field_name="RSS URL")
        feed = audio_hub.add_feed(name=name, rss_url=rss_url, kind=kind)
    except (ValueError, UrlValidationError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]+[/green] {feed['name']} [dim]({feed['kind']} · {feed['id']})[/dim]")


@hub_app.callback(invoke_without_command=True)
def hub_list(
    ctx: typer.Context,
    kind: Annotated[str | None, typer.Option("--type", "-t", help="Lọc podcast/story/broadcast")] = None,
) -> None:
    """Hiển thị Audio Hub library."""
    if ctx.invoked_subcommand is not None:
        return
    feeds = audio_hub.list_feeds(kind)
    if not feeds:
        console.print("[dim]Audio Hub trống.[/dim]")
        console.print("Thêm bằng: [bold]radio hub add \"Tên podcast\" https://.../rss --type podcast[/bold]")
        return
    table = Table(title="Audio Hub", show_lines=True)
    table.add_column("#", justify="right", width=4)
    table.add_column("ID", style="cyan")
    table.add_column("Tên", style="bold")
    table.add_column("Type")
    table.add_column("RSS", overflow="fold")
    for index, feed in enumerate(feeds, 1):
        table.add_row(str(index), feed["id"], feed["name"], feed.get("kind", "podcast"), feed["rss_url"])
    console.print(table)
    console.print("\n[dim]Xem tập: [bold]radio hub episodes <id>[/bold] | Phát: [bold]radio hub play <id> --pick 1 --bg[/bold][/dim]")


def _hub_episode_table(episodes: list[dict[str, Any]], *, title: str) -> None:
    table = Table(title=title, show_lines=False)
    table.add_column("#", justify="right", width=4)
    table.add_column("Tập", style="bold")
    table.add_column("Ngày")
    table.add_column("Thời lượng")
    for index, episode in enumerate(episodes, 1):
        table.add_row(str(index), episode["title"], episode.get("published", ""), episode.get("duration", ""))
    console.print(table)


def _hub_feed_or_exit(feed_id: str) -> dict[str, Any]:
    feed = audio_hub.get_feed(feed_id)
    if feed is None:
        console.print(f"[red]Không tìm thấy feed:[/red] {feed_id}")
        raise typer.Exit(1)
    return feed


def _hub_episode_or_exit(feed_id: str, index: int) -> dict[str, Any]:
    try:
        episode = audio_hub.get_episode(feed_id, index)
    except Exception as exc:
        console.print(f"[red]Không tải được RSS feed:[/red] {exc}")
        raise typer.Exit(1) from exc
    if episode is None:
        console.print(f"[red]Không có tập số {index}.[/red]")
        raise typer.Exit(1)
    return episode


@hub_app.command("episodes")
def hub_episodes(
    feed_id: Annotated[str, typer.Argument(help="ID hoặc tên feed")],
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=50, help="Số tập hiển thị")] = 20,
) -> None:
    """Xem episode/chapter mới nhất từ RSS feed."""
    feed = _hub_feed_or_exit(feed_id)
    try:
        episodes = audio_hub.fetch_episodes(feed, limit=limit)
    except Exception as exc:
        console.print(f"[red]Không tải được RSS feed:[/red] {exc}")
        raise typer.Exit(1) from exc
    if not episodes:
        console.print("[yellow]Feed không có episode audio hợp lệ.[/yellow]")
        raise typer.Exit(1)
    _hub_episode_table(episodes, title=f"{feed['name']} · {feed.get('kind', 'podcast')}")


@hub_app.command("play")
def hub_play(
    feed_id: Annotated[str, typer.Argument(help="ID hoặc tên feed")],
    pick: Annotated[int, typer.Option("--pick", "-p", help="Chọn tập theo số")] = 1,
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Phát một episode/chapter trong Audio Hub."""
    episode = _hub_episode_or_exit(feed_id, pick)
    display.show_playback_panel(episode["title"], subtitle=f"Audio Hub · {episode.get('source', 'podcast')}", background=background)
    _run_player_or_exit(episode["url"], title=episode["title"], source=episode.get("source", "podcast"), background=background, quiet=not background)


@hub_app.command("queue")
def hub_queue(
    feed_id: Annotated[str, typer.Argument(help="ID hoặc tên feed")],
    pick: Annotated[int, typer.Option("--pick", "-p", help="Chọn tập theo số")] = 1,
) -> None:
    """Thêm một episode/chapter vào queue."""
    episode = _hub_episode_or_exit(feed_id, pick)
    item = queue_store.make_item(title=episode["title"], url=episode["url"], source=episode.get("source", "podcast"))
    if queue_store.has_url(item["url"]):
        console.print(f"[yellow]=[/yellow] Đã có trong queue: {item['title']}")
        return
    total = queue_store.add_item(item)
    console.print(f"[green]+[/green] {item['title']} [dim]({total} mục)[/dim]")


@hub_app.command("remove")
def hub_remove(
    feed_id: Annotated[str, typer.Argument(help="ID feed cần xóa")],
) -> None:
    """Xóa một feed khỏi Audio Hub."""
    removed = audio_hub.remove_feed(feed_id)
    if removed is None:
        console.print(f"[red]Không tìm thấy feed:[/red] {feed_id}")
        raise typer.Exit(1)
    console.print(f"[dim]Đã xóa feed:[/dim] {removed['name']}")


@fav_app.command("list")
def fav_list() -> None:
    """Danh sách yêu thích (kênh + bài hát)."""
    station_ids = favorites.list_station_ids()
    tracks = favorites.list_tracks()

    if not station_ids and not tracks:
        console.print("[dim]Chưa có yêu thích.[/dim]")
        console.print("Thêm kênh: [bold]radio fav add vov3[/bold]")
        console.print("Thêm bài: [bold]radio search \"sơn tùng\" --fav[/bold]")
        return

    if station_ids:
        console.print("[bold]Kênh yêu thích[/bold]")
        fav_stations = [s for s in stations.load_stations() if s["id"] in station_ids]
        display.show_station_table(fav_stations, favorite_ids=set(station_ids))

    if tracks:
        console.print()
        display.show_fav_tracks_table(tracks)


@fav_app.command("add")
def fav_add(
    station_id: Annotated[str, typer.Argument(help="ID kênh (vd: vov3)")],
) -> None:
    """Thêm kênh radio vào yêu thích."""
    if not favorites.add_station(station_id):
        console.print(f"[red]Kênh không tồn tại: {station_id}[/red]")
        raise typer.Exit(1)
    station = stations.station_by_id(station_id)
    name = station["name"] if station else station_id
    console.print(f"[green]★[/green] Đã thêm: [bold]{name}[/bold]")


@fav_app.command("remove")
def fav_remove(
    station_id: Annotated[str, typer.Argument(help="ID kênh cần xóa")],
) -> None:
    """Xóa kênh khỏi yêu thích."""
    if favorites.remove_station(station_id):
        console.print(f"[dim]Đã xóa: {station_id}[/dim]")
    else:
        console.print(f"[yellow]Không có trong yêu thích: {station_id}[/yellow]")
        raise typer.Exit(1)


@fav_app.command("play")
def fav_play(
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Chọn và phát kênh radio yêu thích."""
    station_ids = favorites.list_station_ids()
    fav_stations = [s for s in stations.load_stations() if s["id"] in station_ids]

    if not fav_stations:
        console.print("[yellow]Chưa có kênh yêu thích.[/yellow]")
        console.print("Thêm bằng: [bold]radio fav add vov3[/bold]")
        raise typer.Exit(1)

    display.show_station_table(fav_stations, favorite_ids=set(station_ids))
    choice = display.pick_from_list(len(fav_stations), "Chọn kênh yêu thích")
    _play_station(fav_stations[choice - 1], background=background)


@fav_app.command("play-track")
def fav_play_track(
    pick: Annotated[
        int | None, typer.Option("--pick", "-p", help="Chọn bài theo số (1-N)")
    ] = None,
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Chọn và phát bài hát V-Pop yêu thích."""
    tracks = favorites.list_tracks()
    if not tracks:
        console.print("[yellow]Chưa có bài hát yêu thích.[/yellow]")
        console.print('Thêm bằng: [bold]radio search "sơn tùng" --fav[/bold]')
        raise typer.Exit(1)

    display.show_fav_tracks_table(tracks)
    index = pick if pick is not None else display.pick_from_list(len(tracks), "Chọn bài yêu thích")
    if index < 1 or index > len(tracks):
        console.print(f"[red]Số lựa chọn không hợp lệ:[/red] {index}")
        raise typer.Exit(1)
    track = tracks[index - 1]

    display.show_playback_panel(track["title"], subtitle="V-Pop · Yêu thích", background=background)
    _run_player_or_exit(
        track["url"],
        title=track["title"],
        source="search",
        background=background,
        quiet=not background,
    )


@history_app.callback(invoke_without_command=True)
def history_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Số mục hiển thị")] = 20,
) -> None:
    """Hiển thị lịch sử nghe."""
    if ctx.invoked_subcommand is not None:
        return

    entries = history.list_entries()[:limit]
    if not entries:
        console.print("[dim]Chưa có lịch sử.[/dim]")
        console.print("Nghe radio hoặc search V-Pop để lưu tự động.")
        return

    display.show_history_table(entries)
    console.print("\n[dim]Phát lại: [bold]radio history play <số>[/bold] | Xóa: [bold]radio history remove <số>[/bold][/dim]")


@history_app.command("play")
def history_play(
    index: Annotated[int, typer.Argument(help="Số thứ tự trong lịch sử (1-N)")],
    background: Annotated[bool, typer.Option("--bg", "-b", help="Phát nền")] = False,
) -> None:
    """Phát lại mục từ lịch sử."""
    entry = history.get_entry(index)
    if entry is None:
        console.print(f"[red]Không có mục số {index} trong lịch sử.[/red]")
        console.print("Xem: [bold]radio history[/bold]")
        raise typer.Exit(1)

    _play_history_entry(entry, background=background)


@history_app.command("remove")
def history_remove(
    index: Annotated[int, typer.Argument(help="Số thứ tự trong lịch sử (1-N)")],
) -> None:
    """Xóa một mục khỏi lịch sử."""
    entry = history.remove(index)
    if entry is None:
        console.print(f"[red]Không có mục số {index} trong lịch sử.[/red]")
        console.print("Xem: [bold]radio history[/bold]")
        raise typer.Exit(1)
    console.print(f"[dim]Đã xóa khỏi lịch sử:[/dim] {entry['title']}")


@history_app.command("clear")
def history_clear(
    force: Annotated[bool, typer.Option("--yes", "-y", help="Không hỏi xác nhận")] = False,
) -> None:
    """Xóa toàn bộ lịch sử."""
    if not force:
        confirm = typer.confirm("Xóa toàn bộ lịch sử nghe?")
        if not confirm:
            raise typer.Exit(0)

    count = history.clear()
    console.print(f"[dim]Đã xóa {count} mục.[/dim]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Lọc kênh theo thể loại")
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", help="Bật debug logging")] = False,
) -> None:
    """Menu tương tác — chọn kênh để nghe."""
    setup_logging(verbose=verbose)
    if ctx.invoked_subcommand is not None:
        return

    all_stations = stations.filter_stations(stations.load_stations(), category)
    fav_ids = set(favorites.list_station_ids())

    if not all_stations:
        console.print("[yellow]Không có kênh nào.[/yellow]")
        raise typer.Exit(1)

    running = player.get_playback_state()
    header = "[bold]Radio Việt Nam CLI[/bold]\nNghe radio & V-Pop trên terminal."
    if running:
        header += f"\n[green]▶ Đang phát:[/green] {running.title} — [bold]radio stop[/bold] để dừng"

    console.print(Panel(header, border_style="blue"))
    display.show_station_table(all_stations, favorite_ids=fav_ids)
    console.print(
        "\n[dim]Lệnh: radio play vov3 --bg | radio random --bg | radio resume | "
        "radio queue add vov3 | radio tui[/dim]"
    )

    choice = display.pick_from_list(len(all_stations), "Chọn kênh để phát")
    _play_station(all_stations[choice - 1], background=False)


if __name__ == "__main__":
    app()
