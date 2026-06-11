from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

from radio_cli import stations
from radio_cli.config import CONFIG_DIR, DATA_DIR, ensure_dirs, mpv_install_hint
from radio_cli.ytdlp_util import ytdlp_version


@dataclass
class DoctorCheck:
    name: str
    ok: bool
    detail: str






@dataclass
class DoctorFix:
    name: str
    ok: bool
    detail: str


def parse_duration_seconds(value: str) -> int:
    raw = value.strip().lower()
    if not raw:
        raise ValueError("duration is empty")

    suffixes = {
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
    }

    number = raw
    multiplier = 60
    for suffix, factor in sorted(suffixes.items(), key=lambda item: len(item[0]), reverse=True):
        if raw.endswith(suffix):
            number = raw[: -len(suffix)].strip()
            multiplier = factor
            break

    try:
        amount = float(number)
    except ValueError as exc:
        raise ValueError(f"invalid duration: {value}") from exc

    seconds = int(amount * multiplier)
    if seconds <= 0:
        raise ValueError("duration must be positive")
    return seconds


def format_duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def _writable_dir_check(path) -> tuple[bool, str]:
    try:
        ensure_dirs()
        probe = path / ".radio-cli-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, str(path)
    except OSError as exc:
        return False, f"{path} ({exc})"


def run_doctor_checks() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    checks.append(
        DoctorCheck(
            "Python",
            sys.version_info >= (3, 10),
            ".".join(str(part) for part in sys.version_info[:3]),
        )
    )

    mpv = shutil.which("mpv")
    checks.append(DoctorCheck("mpv", bool(mpv), mpv or "not found on PATH"))

    try:
        version = ytdlp_version()
    except SystemExit:
        version = None
    checks.append(DoctorCheck("yt-dlp", bool(version), version or "not found"))

    try:
        loaded = stations.load_stations()
        invalid = [s for s in loaded if not s.get("id") or not s.get("url") or not s.get("name")]
        detail = f"{len(loaded)} stations" if not invalid else f"{len(invalid)} invalid stations"
        checks.append(DoctorCheck("stations", bool(loaded) and not invalid, detail))
    except Exception as exc:  # noqa: BLE001 - diagnostic command should report all config errors
        checks.append(DoctorCheck("stations", False, str(exc)))

    for name, path in (("data dir", DATA_DIR), ("config dir", CONFIG_DIR)):
        ok, detail = _writable_dir_check(path)
        checks.append(DoctorCheck(name, ok, detail))

    return checks


def run_doctor_fixes() -> list[DoctorFix]:
    fixes: list[DoctorFix] = []

    ensure_dirs()
    fixes.append(DoctorFix("data/config dirs", True, "Đã đảm bảo thư mục dữ liệu tồn tại."))

    if shutil.which("mpv"):
        fixes.append(DoctorFix("mpv", True, "mpv đã có trên PATH."))
    else:
        fixes.append(DoctorFix("mpv", False, mpv_install_hint()))

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fixes.append(DoctorFix("yt-dlp", False, f"Không thể cập nhật yt-dlp: {exc}"))
    else:
        detail = (proc.stdout or proc.stderr or "").strip().splitlines()
        last_line = detail[-1] if detail else "pip không trả output."
        fixes.append(DoctorFix("yt-dlp", proc.returncode == 0, last_line))

    return fixes
