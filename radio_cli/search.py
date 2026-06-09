from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from rich.console import Console

from radio_cli.ytdlp_util import YtdlpError, _ytdlp_argv, ytdlp_argv

console = Console()


class SearchError(Exception):
    """Lỗi search không ghi ra terminal (dùng từ TUI)."""


@dataclass
class SearchResult:
    title: str
    video_id: str
    duration: str
    url: str

    @property
    def watch_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def _search_failure_message(stderr: str) -> str:
    if stderr:
        return stderr.strip().splitlines()[-1]
    return "Tìm kiếm thất bại. Kiểm tra mạng hoặc yt-dlp."


def _run_ytdlp_search(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SearchError("yt-dlp search quá thời gian chờ.") from exc
    except OSError as exc:
        raise SearchError(f"Không thể chạy yt-dlp: {exc}") from exc


def search_vpop(query: str, limit: int = 10, *, quiet: bool = False) -> list[SearchResult]:
    """Tìm bài hát V-Pop trên YouTube qua yt-dlp."""
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50")

    if quiet:
        try:
            ytdlp = _ytdlp_argv(quiet=True)
        except YtdlpError as exc:
            raise SearchError(str(exc)) from exc
    else:
        ytdlp = ytdlp_argv()

    search_query = f"ytsearch{limit}:{query} vpop nhạc việt"
    try:
        proc = _run_ytdlp_search(
            [
                *ytdlp,
                search_query,
                "--flat-playlist",
                "--no-warnings",
                "--print",
                "%(title)s\t%(id)s\t%(duration_string)s",
            ]
        )
    except SearchError as exc:
        if quiet:
            raise
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    if proc.returncode != 0:
        try:
            proc = _run_ytdlp_search([*ytdlp, search_query, "--flat-playlist", "--no-warnings", "-j"])
        except SearchError as exc:
            if quiet:
                raise
            console.print(f"[red]{exc}[/red]")
            raise SystemExit(1) from exc
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            message = _search_failure_message(stderr)
            if quiet:
                raise SearchError(message)
            console.print("[red]Tìm kiếm thất bại. Kiểm tra mạng hoặc yt-dlp.[/red]")
            if stderr:
                console.print(f"[dim]{stderr}[/dim]")
            raise SystemExit(1)

        results: list[SearchResult] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = item.get("id", "")
            if not vid:
                continue
            results.append(
                SearchResult(
                    title=item.get("title", "Không rõ"),
                    video_id=vid,
                    duration=item.get("duration_string") or "--:--",
                    url=f"https://www.youtube.com/watch?v={vid}",
                )
            )
        return results

    results = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        title, vid = parts[0], parts[1]
        duration = parts[2] if len(parts) > 2 else "--:--"
        results.append(
            SearchResult(
                title=title,
                video_id=vid,
                duration=duration or "--:--",
                url=f"https://www.youtube.com/watch?v={vid}",
            )
        )
    return results
