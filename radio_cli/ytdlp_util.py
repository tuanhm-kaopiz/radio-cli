from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console

console = Console()

# Format ưu tiên audio-only, fallback linh hoạt.
AUDIO_FORMAT = "bestaudio[ext=m4a]/bestaudio/best"


class YtdlpError(Exception):
    """Lỗi yt-dlp không ghi ra terminal (dùng từ TUI)."""


def is_youtube_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    host = (parsed.netloc or parsed.path.split("/", 1)[0]).lower()
    if ":" in host:
        host = host.split(":", 1)[0]
    return (
        host == "youtu.be"
        or host.endswith(".youtu.be")
        or host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtube-nocookie.com"
        or host.endswith(".youtube-nocookie.com")
    )


def _ytdlp_argv(*, quiet: bool = False) -> list[str]:
    """Ưu tiên yt-dlp cùng Python env (pip), sau đó binary trên PATH."""
    try:
        import yt_dlp  # noqa: F401

        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        pass

    radio_bin = shutil.which("radio")
    if radio_bin:
        sibling_path = Path(radio_bin).parent / "yt-dlp"
        if sibling_path.is_file():
            return [str(sibling_path)]

    found = shutil.which("yt-dlp")
    if found:
        return [found]

    if not quiet:
        console.print(
            "[red]Không tìm thấy yt-dlp.[/red]\n"
            "Cài đặt: [bold]pip install -U yt-dlp[/bold] hoặc [bold]sudo apt install yt-dlp[/bold]"
        )
    raise YtdlpError("Không tìm thấy yt-dlp")


def ytdlp_argv() -> list[str]:
    try:
        return _ytdlp_argv(quiet=False)
    except YtdlpError:
        raise SystemExit(1) from None


def ytdlp_version() -> str | None:
    try:
        argv = _ytdlp_argv(quiet=True)
    except YtdlpError:
        return None
    try:
        proc = subprocess.run(
            [*argv, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _ytdlp_too_old(version: str) -> bool:
    # YouTube thường break yt-dlp < 2025
    try:
        year = int(version.split(".", 1)[0])
        return year < 2025
    except (ValueError, IndexError):
        return False


def _stream_error_message(stderr: str) -> str:
    if "Requested format is not available" in stderr or "Signature extraction" in stderr:
        return "YouTube đã đổi — cần cập nhật yt-dlp (pip install -U yt-dlp)."
    if stderr:
        return stderr.splitlines()[-1]
    return "Không lấy được stream YouTube."


def resolve_stream_url(url: str, *, quiet: bool = False) -> str:
    """Lấy URL audio trực tiếp từ YouTube; URL khác giữ nguyên."""
    if not is_youtube_url(url):
        return url

    argv = _ytdlp_argv(quiet=quiet)

    version = ytdlp_version()
    if version and _ytdlp_too_old(version) and not quiet:
        console.print(
            f"[yellow]yt-dlp {version} có thể quá cũ cho YouTube.[/yellow]\n"
            "Khuyến nghị: [bold]pip install -U yt-dlp[/bold]"
        )

    try:
        proc = subprocess.run(
            [*argv, "-f", AUDIO_FORMAT, "--no-playlist", "--no-warnings", "-g", url],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        message = "yt-dlp lấy stream quá thời gian chờ."
        if quiet:
            raise YtdlpError(message) from exc
        console.print(f"[red]{message}[/red]")
        raise SystemExit(1) from exc
    except OSError as exc:
        message = f"Không thể chạy yt-dlp: {exc}"
        if quiet:
            raise YtdlpError(message) from exc
        console.print(f"[red]{message}[/red]")
        raise SystemExit(1) from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        message = _stream_error_message(stderr)
        if quiet:
            raise YtdlpError(message)
        console.print("[red]Không lấy được stream YouTube.[/red]")
        if "Requested format is not available" in stderr or "Signature extraction" in stderr:
            console.print(
                "YouTube đã đổi — cần cập nhật yt-dlp:\n"
                "  [bold]pip install -U yt-dlp[/bold]\n"
                "  hoặc trong venv: [bold]pip install -U yt-dlp[/bold] rồi [bold]pip install -e .[/bold]"
            )
        elif stderr:
            console.print(f"[dim]{stderr.splitlines()[-1]}[/dim]")
        raise SystemExit(1)

    stream_urls = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("http")]
    if not stream_urls:
        if quiet:
            raise YtdlpError("Không tìm thấy URL audio từ YouTube.")
        console.print("[red]Không tìm thấy URL audio từ YouTube.[/red]")
        raise SystemExit(1)

    # -g có thể trả về 1 (audio) hoặc 2 dòng (video+audio); lấy dòng cuối thường là audio
    return stream_urls[-1]
