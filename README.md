# radio-cli

**Nghe radio Việt Nam và V-Pop ngay trên terminal** — Python + mpv + yt-dlp. Hỗ trợ **Linux, macOS và Windows**.

Ứng dụng dòng lệnh nhẹ, không cần GUI. Phát radio trực tiếp (VOV3, M Radio…), tìm bài V-Pop như Spotify CLI, chạy nền trong khi bạn code hoặc làm việc.

```bash
radio list
radio play vov3 --bg
radio search "sơn tùng mtp" --play
radio queue add vov3 m-radio
radio next --bg
radio playlist import "Danh sách yêu thích 1" examples/playlist_import_sample.txt --create
radio playlist play "Danh sách yêu thích 1" --bg
radio export-data backup.json
radio tui
radio stop
```

> **Nền tảng:** Linux · macOS · Windows. One-line installer tự cài Python deps, `yt-dlp`, Textual TUI và cấu hình lệnh `radio` global; `mpv` được cài tự động trên Linux/macOS nếu package manager hỗ trợ.

---

## Mục lục

- [Tính năng](#tính-năng)
- [Yêu cầu](#yêu-cầu)
- [Cài đặt nhanh](#cài-đặt-nhanh)
- [Cài đặt chi tiết](#cài-đặt-chi-tiết)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Danh sách kênh](#danh-sách-kênh)
- [Cấu hình & dữ liệu người dùng](#cấu-hình--dữ-liệu-người-dùng)
- [Gỡ cài đặt](#gỡ-cài-đặt)
- [Thêm kênh radio](#thêm-kênh-radio)
- [Xử lý sự cố](#xử-lý-sự-cố)
- [Đóng góp](#đóng-góp)
- [Giấy phép & lưu ý](#giấy-phép--lưu-ý)

---

## Tính năng

| Tính năng | Mô tả |
|---|---|
| Radio Việt Nam | VOV3, M Radio, VOV2, VOV5, VOV Giao thông… |
| Phát nền | `radio play vov3 --bg` — trả terminal ngay |
| Dừng / trạng thái | `radio stop`, `radio status` từ bất kỳ tab terminal |
| Yêu thích | Lưu kênh radio và bài V-Pop |
| Tìm V-Pop | `radio search` qua YouTube (yt-dlp) + mpv |
| Menu tương tác | Gõ `radio` để chọn kênh bằng số |
| Pause / Volume | `radio pause`, `radio vol 70` (IPC đa nền tảng) |
| Lịch sử | `radio history`, `radio history play 1`, `radio resume` |
| Premium Core | `radio random`, `radio sleep 30m`, `radio doctor`, tìm kênh gần đúng |
| Premium Player | Queue/playlist local: `radio queue add`, `radio next`, `radio dashboard` |
| TUI Player | Fullscreen player: `radio tui` với Stations, YouTube Search, Queue, History và phím tắt |
| Mở rộng | Thêm kênh trong `radio_cli/data/stations.json` với tags, aliases, fallback URLs |

---

## Yêu cầu

| Phần mềm | Bắt buộc | Dùng cho |
|---|---|---|
| Python ≥ 3.10 | Có | Chạy CLI |
| [mpv](https://mpv.io/) | Có | Phát audio |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Có | Lệnh `radio search` |

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip mpv yt-dlp
```

### Fedora

```bash
sudo dnf install -y git python3 mpv yt-dlp
```

### Arch Linux

```bash
sudo pacman -S git python mpv yt-dlp
```

### macOS

```bash
brew install git python mpv yt-dlp
```

### Windows

1. Cài [Python 3.10+](https://www.python.org/downloads/) (tick **Add to PATH**)
2. Cài [mpv](https://mpv.io/installation/) — thêm `mpv.exe` vào PATH
3. Trong PowerShell:

```powershell
pip install yt-dlp
git clone https://github.com/tuanhm-kaopiz/radio-cli.git
cd radio-cli
python -m venv venv
.\venv\Scripts\activate
pip install -e .
radio list
```

Kiểm tra sau khi cài:

```bash
python3 --version   # >= 3.10
mpv --version
yt-dlp --version
```

---

## Cài đặt nhanh

Chỉ một lệnh duy nhất:

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/tuanhm-kaopiz/radio-cli@main/install.sh | bash
```

> **Lưu ý:** `raw.githubusercontent.com` đôi khi cache bản `install.sh` cũ sau khi push. Nếu vẫn thấy `YOUR_USERNAME`, dùng lệnh **jsDelivr** ở trên hoặc:
> ```bash
> rm -rf ~/.local/share/radio-cli/app
> curl -fsSL https://raw.githubusercontent.com/tuanhm-kaopiz/radio-cli/main/install.sh | \
>   RADIO_CLI_REPO=https://github.com/tuanhm-kaopiz/radio-cli.git bash
> ```

Sau khi cài xong, mở terminal mới hoặc chạy dòng mà installer in ra, rồi dùng ngay:

```bash
radio tui
```

Installer tự động:

| Việc | Ghi chú |
|---|---|
| Cài dependency hệ thống | `git`, Python, `mpv` qua `apt`, `dnf`, `pacman`, `zypper` hoặc Homebrew nếu có |
| Clone/update app | `~/.local/share/radio-cli/app` |
| Tạo virtualenv riêng | Không đụng Python global |
| Cài full tính năng | Typer, Rich, Textual TUI, yt-dlp |
| Tạo lệnh global | Ưu tiên `/usr/local/bin/radio`, fallback `~/.local/bin/radio` |
| Tự cấu hình PATH | Chỉ thêm `~/.local/bin` vào `~/.bashrc` hoặc `~/.zshrc` nếu phải dùng fallback local |
| Kiểm tra sau cài | Tự chạy `radio doctor` |

Cài từ source local (dev / không qua curl):

```bash
bash "/đường/dẫn/radio-cli/install.sh"
```

Nghe thử ngay:

```bash
radio play vov3 --bg
radio status
radio stop
```

---

## Cài đặt chi tiết

### Bước 1 — Clone repository

```bash
git clone https://github.com/tuanhm-kaopiz/radio-cli.git
cd radio-cli
```

### Bước 2 — Virtual environment (khuyến nghị)

Tránh xung đột package Python trên hệ thống:

```bash
python3 -m venv venv
source venv/bin/activate        # bash/zsh
# source venv/bin/activate.fish # fish shell
```

Mỗi lần mở terminal mới, kích hoạt lại:

```bash
cd radio-cli
source venv/bin/activate
```

### Bước 3 — Cài package

```bash
pip install --upgrade pip
pip install -e .
```

Lệnh `radio` sẽ nằm trong `venv/bin/radio`.

### Bước 4 — Dùng `radio` mọi nơi (tùy chọn)

**Cách A — Symlink** (khuyến nghị, tránh lỗi path có khoảng trắng):

```bash
ln -sf "/đường/dẫn/đầy/đủ/radio-cli/venv/bin/radio" ~/.local/bin/radio
# Ví dụ:
# ln -sf "/var/www/Vibe Coding/radio-cli/venv/bin/radio" ~/.local/bin/radio
```

**Cách B — Alias** (phải trỏ **đúng** thư mục clone, dùng dấu ngoặc kép):

```bash
alias radio='"/đường/dẫn/đầy/đủ/radio-cli/venv/bin/radio"'
```

**Cách C — PATH** (thêm `venv/bin` vào PATH):

```bash
echo 'export PATH="/đường/dẫn/đầy/đủ/radio-cli/venv/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Cách D — Shell completion** (tab gợi ý lệnh):

```bash
radio --install-completion bash   # hoặc zsh, fish
# làm theo hướng dẫn in ra màn hình
```

### Bước 5 — Xác nhận cài đặt

```bash
radio --help
radio list
which radio    # nên trỏ tới venv/bin/radio nếu dùng venv
```

---

## Hướng dẫn sử dụng

### Tổng quan lệnh

```
radio                          Menu chọn kênh (tương tác)
radio list                     Danh sách kênh
radio play <id>                Phát radio (foreground)
radio play <id> --bg           Phát nền
radio stop                     Dừng phát
radio status                   Đang phát gì?
radio search "<từ khóa>"       Tìm V-Pop
radio fav add <id>             Thêm kênh yêu thích
radio fav list                 Xem yêu thích
radio fav play                 Phát từ yêu thích
radio playlist                 Danh sách playlist cá nhân
radio playlist create <tên>    Tạo playlist mới
radio playlist import <tên> <file.txt> [--create]   Import link từ file text
radio playlist show <tên>      Xem bài trong playlist
radio playlist play <tên> [--bg] [--replace-queue]  Phát playlist
radio playlist shuffle <tên>   Trộn rồi phát
radio export-data backup.json  Backup toàn bộ dữ liệu (gồm playlist)
radio import-data backup.json [--merge]  Khôi phục dữ liệu từ backup
radio random                   Phát ngẫu nhiên một kênh
radio resume                   Phát lại mục gần nhất
radio sleep 30m                Hẹn giờ dừng player
radio doctor                   Kiểm tra môi trường
radio queue add <id/url>       Thêm mục vào queue
radio queue                    Xem queue
radio next                     Phát mục tiếp theo
radio dashboard                Xem dashboard player
radio tui                      Mở TUI player fullscreen
```

---

### Menu tương tác

```bash
radio
radio -c nhac-tre    # chỉ kênh nhạc trẻ
```

Nhập số kênh → phát trực tiếp. **Ctrl+C** để dừng.

---

### `radio list`

```bash
radio list
radio list -c nhac-tre
radio list -c giai-tri
radio list -c giao-thong
radio list -f                 # chỉ kênh đã ★ yêu thích
```

| Mã thể loại | Tên hiển thị |
|---|---|
| `nhac-tre` | Nhạc trẻ |
| `giai-tri` | Giải trí |
| `giao-thong` | Giao thông |

---

### `radio play`

```bash
# Foreground — terminal bị chặn, Ctrl+C để dừng
radio play vov3
radio play m-radio

# Background — làm việc tiếp trên terminal
radio play vov3 --bg
radio play vov3 -b

# Stream URL tùy ý
radio play "https://str.vov.gov.vn/vovlive/vov3.sdp_aac/playlist.m3u8" --bg
```

---

### `radio stop` & `radio status`

```bash
radio play vov3 --bg
radio status     # xem tên kênh, PID, URL
radio stop       # dừng — gọi được từ terminal/tab khác
```

Trạng thái lưu tại `~/.local/share/radio-cli/` nên `stop` / `status` hoạt động cross-terminal.

---

### Premium Core: random / resume / sleep / doctor

```bash
radio random --bg              # phát ngẫu nhiên một kênh
radio random -c traffic --bg   # random theo tag/thể loại/thành phố
radio resume --bg              # phát lại mục gần nhất trong history
radio sleep 30m                # dừng player sau 30 phút
radio doctor                   # kiểm tra Python, mpv, yt-dlp, dữ liệu local
```

`radio sleep` chạy foreground để giữ timer rõ ràng; nhấn Ctrl+C để hủy hẹn giờ, player vẫn tiếp tục chạy.

---

### Audio Hub: podcast / truyện / broadcast

```bash
radio hub add "Ten podcast" https://example.com/feed.xml --type podcast
radio hub add "Truyen dem khuya" https://example.com/story.xml --type story
radio hub
radio hub episodes ten-podcast
radio hub play ten-podcast --pick 1 --bg
radio hub queue ten-podcast --pick 2
```

Audio Hub dùng RSS feed chuẩn, lưu library local và phát episode/chapter bằng cùng player/queue/TUI. Source mới gồm `podcast`, `story`, `broadcast`; TUI sẽ hiển thị icon riêng và điều khiển như nhạc YouTube.

---

### Premium Player: queue / next / dashboard

```bash
radio queue add vov3 m-radio   # thêm nhiều kênh vào queue, tự bỏ qua mục trùng
radio queue add "https://example.com/live.m3u8"
radio queue                    # xem queue
radio queue play --pick 2 --bg # phát mục số 2 và xóa khỏi queue
radio next --bg                # lấy mục đầu queue để phát
radio queue remove 1
radio queue clear --yes
radio dashboard                # snapshot Now Playing + Queue + History
radio dashboard --watch        # tự refresh, Ctrl+C để thoát
```

Queue được lưu local trong thư mục dữ liệu người dùng, giống history/player state.

---

### Playlist cá nhân: import/export link YouTube

Playlist là danh sách phát đặt tên và lưu bền vững, khác với queue tạm thời. Dùng khi bạn muốn có các bộ sưu tập như `Danh sách yêu thích 1`, `Nhạc làm việc`, `V-Pop chill`.

```bash
radio playlist create "Danh sách yêu thích 1"
radio playlist add "Danh sách yêu thích 1" "https://www.youtube.com/watch?v=..." --title "Tên bài"
radio playlist import "Danh sách yêu thích 1" examples/playlist_import_sample.txt --create
radio playlist
radio playlist show "Danh sách yêu thích 1"
radio playlist play "Danh sách yêu thích 1" --bg
radio playlist shuffle "Danh sách yêu thích 1" --bg
radio playlist remove "Danh sách yêu thích 1" 2
radio playlist delete "Danh sách yêu thích 1" --yes
```

File import là text UTF-8, mỗi dòng là một URL hoặc `Tên bài | URL`:

```txt
# comment sẽ được bỏ qua
Sơn Tùng M-TP - Chúng ta của tương lai | https://www.youtube.com/watch?v=...
https://youtu.be/...
```

Mẫu có sẵn: [`examples/playlist_import_sample.txt`](examples/playlist_import_sample.txt).

Khi chạy `playlist play`, bài đầu tiên phát ngay; các bài còn lại được nạp vào queue để `radio next` hoặc autoplay trong TUI dùng tiếp. Thêm `--replace-queue` nếu muốn xóa queue hiện tại trước khi nạp playlist.

---

### TUI Player

```bash
radio tui
```

Phím chính trong TUI:

| Phím | Hành động |
|---|---|
| `Tab` / `Shift+Tab` hoặc `l` / `h` | Chuyển panel Stations / Search / Queue / Playlists / History |
| `↑`/`↓` hoặc `k`/`j` | Di chuyển lựa chọn |
| `/` | Search YouTube trong TUI |
| `Enter` | Phát mục đang chọn ở nền |
| `a` | Thêm station hoặc kết quả search đang chọn vào queue, bỏ qua nếu đã có |
| `p` | Lưu mục đang chọn vào playlist mặc định `Danh sách yêu thích 1` |
| `d` / `x` / `Delete` | Xóa mục đang chọn khỏi Queue hoặc History |
| `n` | Phát mục tiếp theo trong queue |
| `[` / `]` | Tua lùi / tua tới 10 giây |
| `0` | Phát lại bài hiện tại từ đầu |
| `m` | Mute / unmute |
| `Space` | Pause / resume |
| `s` | Stop player |
| `+` / `-` | Tăng / giảm volume |
| `r` | Refresh |
| `q` | Thoát TUI |

---

### `radio search` — V-Pop on-demand

```bash
# Chọn bài từ danh sách (tương tác)
radio search "sơn tùng mtp"

# Tùy chọn
radio search "nơi này có anh" -n 5          # tối đa 5 kết quả
radio search "đen vâu" --pick 2             # chọn bài số 2
radio search "mono" --play                  # phát bài đầu tiên
radio search "sơn tùng" --play --bg         # phát nền
radio search "chúng ta của tương lai" --fav   # lưu yêu thích sau khi chọn
```

> Cần `yt-dlp` và kết nối Internet. Nội dung phát từ YouTube — tuân thủ điều khoản sử dụng của nền tảng.

---

### `radio fav` — Yêu thích

```bash
radio fav add vov3
radio fav remove vov3
radio fav list
radio fav play
radio fav play --bg
```

Bài hát lưu yêu thích qua: `radio search "..." --fav`

---

## Workflow thường dùng

**Nghe radio khi code:**

```bash
radio play vov3 --bg
# ... code ...
radio stop
```

**Nghe một bài V-Pop cụ thể:**

```bash
radio search "nơi này có anh" --pick 1 --bg
radio stop
```

**Kênh hay nghe mỗi ngày:**

```bash
radio fav add vov3
radio fav add m-radio
radio fav play --bg
```

---

## Danh sách kênh

| ID | Kênh | Tần số | Thể loại |
|---|---|---|---|
| `vov3` | VOV3 - Âm nhạc & Sự kiện | 102.7 MHz | Nhạc trẻ |
| `m-radio` | M Radio Giải Trí Việt Nam | Online | Nhạc trẻ |
| `vov2` | VOV2 - Văn hóa & Xã hội | 91.5 MHz | Giải trí |
| `vov5` | VOV5 - Phát thanh đối ngoại | 105.5 MHz | Giải trí |
| `vov-gt-hn` | VOV Giao Thông Hà Nội | 91.0 MHz | Giao thông |
| `vov-gt-hcm` | VOV Giao Thông TP.HCM | 99.9 MHz | Giao thông |

Gõ `radio list` để xem bảng đầy đủ trên terminal.

---

## Cấu hình & dữ liệu người dùng

| File | Linux / macOS | Windows |
|---|---|---|
| Danh sách kênh | `radio_cli/data/stations.json` | `radio_cli/data/stations.json` |
| Yêu thích | `~/.config/radio-cli/favorites.json` | `%APPDATA%\radio-cli\favorites.json` |
| Dữ liệu player | `~/.local/share/radio-cli/` | `%LOCALAPPDATA%\radio-cli\` |

Trong thư mục dữ liệu: `player.pid`, `player.state.json`, `history.json`, `queue.json`, `audio_hub.json`. IPC: Unix socket (Linux/macOS) hoặc named pipe `\\.\pipe\radio-cli-mpv` (Windows).

Dữ liệu người dùng **không** nằm trong repo — mỗi máy tự tạo khi chạy lần đầu.

---

## Gỡ cài đặt

Gỡ **radio-cli** không xóa `mpv`, `yt-dlp` hay Python trên hệ thống — chỉ gỡ app và (tuỳ chọn) dữ liệu cá nhân.

### Bước 0 — Dừng player

```bash
radio stop
```

### Trường hợp 1 — Cài bằng `install.sh` (one-liner)

Installer đặt app tại `~/.local/share/radio-cli/app` và tạo symlink lệnh `radio`.

```bash
# Xóa lệnh global
rm -f ~/.local/bin/radio
sudo rm -f /usr/local/bin/radio   # nếu installer dùng /usr/local/bin

# Xóa mã nguồn + virtualenv do installer tạo
rm -rf ~/.local/share/radio-cli/app

# (Tuỳ chọn) Xóa dữ liệu người dùng: history, queue, yêu thích, player state
rm -rf ~/.local/share/radio-cli
rm -rf ~/.config/radio-cli
```

Nếu installer đã thêm dòng PATH vào shell, mở `~/.zshrc` hoặc `~/.bashrc` và xóa block:

```bash
# radio-cli installer
export PATH="$HOME/.local/bin:$PATH"
```

Chỉ xóa nếu bạn **không** dùng `~/.local/bin` cho tool khác.

Mở terminal mới, rồi kiểm tra:

```bash
which radio    # không còn kết quả
radio --help   # command not found
```

### Trường hợp 2 — Cài thủ công (`git clone` + `pip install -e .`)

```bash
cd /đường/dẫn/radio-cli
source venv/bin/activate   # nếu đang dùng venv

# Gỡ package Python
pip uninstall -y radio-cli

# Xóa symlink (nếu đã tạo)
rm -f ~/.local/bin/radio

# Gỡ alias sai (trong terminal hiện tại)
unalias radio 2>/dev/null

# Xóa alias/path trong ~/.zshrc hoặc ~/.bashrc (nếu có dòng alias radio=...)
# Xóa thư mục project (tuỳ chọn)
cd ..
rm -rf radio-cli

# (Tuỳ chọn) Xóa dữ liệu người dùng
rm -rf ~/.local/share/radio-cli
rm -rf ~/.config/radio-cli
```

### Windows

```powershell
radio stop
Remove-Item -Force "$env:LOCALAPPDATA\radio-cli" -Recurse -ErrorAction SilentlyContinue
Remove-Item -Force "$env:APPDATA\radio-cli" -Recurse -ErrorAction SilentlyContinue
Remove-Item -Force "$env:USERPROFILE\.local\bin\radio.cmd" -ErrorAction SilentlyContinue
# Xóa thư mục clone + venv nếu cài thủ công
```

### Chỉ xóa dữ liệu, giữ app

Muốn reset yêu thích / lịch sử / queue mà **không** gỡ app:

```bash
radio stop
rm -f ~/.local/share/radio-cli/history.json
rm -f ~/.local/share/radio-cli/queue.json
rm -f ~/.local/share/radio-cli/audio_hub.json
rm -f ~/.local/share/radio-cli/player.pid
rm -f ~/.local/share/radio-cli/player.state.json
rm -f ~/.local/share/radio-cli/player.sock
rm -f ~/.config/radio-cli/favorites.json
```

Hoặc xóa sạch toàn bộ thư mục dữ liệu:

```bash
radio stop
rm -rf ~/.local/share/radio-cli ~/.config/radio-cli
```

Sau đó chạy lại `radio` — app tự tạo file mới.

### Lưu ý

| Thành phần | Gỡ cùng radio-cli? |
|---|---|
| `mpv`, `yt-dlp`, Python | Không — cài riêng qua apt/brew |
| Yêu thích, history, queue | Tuỳ chọn — xóa thư mục dữ liệu |
| Repo clone / `~/.local/share/radio-cli/app` | Có — nếu muốn gỡ hẳn |

---

## Thêm kênh radio

Mở `radio_cli/data/stations.json`, thêm object vào mảng `stations`:

```json
{
  "id": "ten-kenh",
  "name": "Tên hiển thị",
  "description": "Mô tả ngắn",
  "category": "nhac-tre",
  "frequency": "102.7 MHz",
  "url": "https://example.com/live/playlist.m3u8",
  "tags": ["vpop", "chill"],
  "aliases": ["ten kenh", "ten-kenh"],
  "city": "Hanoi",
  "country": "VN",
  "homepage": "https://example.com",
  "fallback_urls": []
}
```

| Trường | Bắt buộc | Ghi chú |
|---|---|---|
| `id` | Có | Dùng với `radio play <id>`, không dấu, không khoảng trắng |
| `name` | Có | Tên hiển thị |
| `description` | Không | Mô tả trong UI |
| `category` | Có | `nhac-tre` \| `giai-tri` \| `giao-thong` |
| `frequency` | Không | VD: `102.7 MHz` hoặc `Online` |
| `url` | Có | Stream HLS (`.m3u8`) hoặc URL trực tiếp |
| `tags` | Không | Dùng cho `radio list -c <tag>` và `radio random -c <tag>` |
| `aliases` | Không | Tên gọi khác để `radio play` tìm gần đúng tốt hơn |
| `city` / `country` | Không | Metadata catalog |
| `homepage` | Không | Trang chủ kênh |
| `fallback_urls` | Không | Danh sách URL dự phòng cho version sau / kiểm tra catalog |

Sau khi sửa, chạy lại `radio list` — **không cần** `pip install` lại.

Muốn chia sẻ kênh mới cho cộng đồng → mở [Pull Request](../../pulls) cập nhật `radio_cli/data/stations.json`.

---

## Cấu trúc project

```
radio-cli/
├── README.md
├── pyproject.toml
├── requirements.txt
├── install.sh       # One-line global installer
├── main.py
└── radio_cli/
    ├── cli.py          # Lệnh Typer
    ├── player.py       # mpv, phát nền, PID
    ├── data/stations.json # Kênh radio đóng gói trong package
    ├── stations.py     # Load, normalize, tìm kênh
    ├── premium.py      # Doctor + parser hẹn giờ
    ├── queue_store.py  # Queue/playlist local
    ├── tui.py          # Textual fullscreen player
    ├── favorites.py    # Yêu thích
    ├── search.py       # yt-dlp search
    ├── display.py      # Giao diện Rich
    └── config.py       # Đường dẫn cấu hình
```

Chạy khi phát triển:

```bash
source venv/bin/activate
pip install -e ".[dev]"
python main.py list
pytest
```

---

## Xử lý sự cố

<details>
<summary><strong>Lệnh <code>radio</code> không tìm thấy</strong></summary>

```bash
source venv/bin/activate
which radio
pip install -e .
```

Hoặc dùng đường dẫn đầy đủ: `./venv/bin/radio list`
</details>

<details>
<summary><strong>Không tìm thấy mpv / yt-dlp</strong></summary>

```bash
sudo apt install mpv yt-dlp    # Ubuntu/Debian
which mpv yt-dlp
```
</details>

<details>
<summary><strong>Không phát được stream radio</strong></summary>

1. Kiểm tra mạng: `curl -I "https://str.vov.gov.vn/vovlive/vov3.sdp_aac/playlist.m3u8"`
2. Thử kênh khác: `radio list`
3. Một số stream có thể tạm ngừng — báo [issue](../../issues)
</details>

<details>
<summary><strong><code>radio search</code> lỗi — <code>Requested format is not available</code></strong></summary>

YouTube thường xuyên đổi API; **yt-dlp cũ** (vd. bản `apt` 2024) sẽ không phát được.

```bash
source venv/bin/activate
pip install -U yt-dlp
pip install -e .
```

`pip install -e .` đã kèm `yt-dlp>=2025` — ưu tiên dùng bản trong venv, không phụ thuộc `apt`.

Nếu vẫn lỗi: thử từ khóa khác, kiểm tra Internet.
</details>

<details>
<summary><strong>Phát nền (<code>--bg</code>) nhưng không nghe thấy</strong></summary>

- Kiểm tra volume hệ thống (PulseAudio / PipeWire)
- Thử foreground để xem lỗi: `radio play vov3` (bỏ `--bg`)
- `radio status` xem process còn chạy không
</details>

<details>
<summary><strong><code>radio stop</code> báo không có gì đang phát</strong></summary>

Player có thể đã tự thoát (lỗi mạng, hết stream). File PID sẽ được dọn nếu process không còn sống.
</details>

---

## Đóng góp

Mọi đóng góp đều welcome!

1. Fork repository
2. Tạo branch: `git checkout -b feature/ten-tinh-nang`
3. Commit thay đổi
4. Push và mở Pull Request

**Gợi ý đóng góp:**

- Thêm kênh radio vào `radio_cli/data/stations.json` (kèm URL stream đã test)
- Sửa lỗi phát stream / search
- Cải thiện README hoặc thêm shell completion

Trước khi PR thêm kênh, xác nhận stream hoạt động:

```bash
mpv --no-video "URL_STREAM"   # Ctrl+C sau vài giây
```

---

## Chuẩn bị đưa lên GitHub

Nếu bạn là maintainer, đảm bảo **không** commit các thư mục sau — thêm `.gitignore`:

```
venv/
__pycache__/
*.egg-info/
.pytest_cache/
```

File `.gitignore` mẫu nên có sẵn trong repo trước khi `git push`.

---

## Giấy phép & lưu ý

- Tool này là phần mềm CLI mã nguồn mở — kiểm tra file `LICENSE` trong repo (nếu có).
- **Nội dung radio** thuộc bản quyền các đài phát thanh (VOV, M Radio, …). Tool chỉ giúp truy cập stream công khai.
- **Tính năng search V-Pop** truy vấn YouTube qua `yt-dlp`. Người dùng chịu trách nhiệm tuân thủ [Điều khoản YouTube](https://www.youtube.com/static?template=terms) và luật bản quyền tại quốc gia của mình.

---

<p align="center">
  Made with Python, mpv & yt-dlp — nghe nhạc Việt trên terminal.
</p>
