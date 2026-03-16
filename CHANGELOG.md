# Changelog

All notable changes to PurposeOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Planned
- Unix socket IPC between CLI/GUI and daemon (replacing config-file-based reload)
- Structured JSON logging with log rotation
- Streak tracking and time-of-day focus patterns in Stats
- `adctl stats export` — CSV export of response-time data

---

## [1.0.0] — 2025

### Added

#### Daemon
- Background systemd user service (`purposeos.service`) that starts on login and restarts on failure
- APScheduler-based trigger engine supporting four trigger types: fixed time (`daily`), repeating interval (`interval_minutes`), weekly by day-of-week, and on-boot
- inotify config watcher — live config reload without daemon restart via `adctl reload`

#### Reminders
- Time-based and interval reminders with configurable urgency (`low` / `normal` / `critical`)
- Screen-wide fullscreen GTK4 overlay notifications or standard libnotify popups, switchable per reminder
- Auto-close timeout configurable globally and per reminder

#### Actions
- Scheduled system actions: `open_file`, `open_app`, `run_command`, `open_url`, `show_notification`
- Per-action enable/disable toggle without deletion
- Daemon records each action launch to SQLite (`is_daemon_launch = 1`)

#### Notes
- Plain-text note storage under `~/.config/automation-daemon/notes/` (or a custom path)
- Curses terminal editor via `adctl notes new` / `adctl notes edit`
- Quick-capture floating window (`adctl quicknote`, Ctrl+Shift+P) for capturing thoughts without leaving the current context

#### Stats
- Per-reminder response-time tracking: seconds from notification display to Done click, stored in `notification_interactions.response_sec`
- Weekly trend view comparing this week vs. last week per reminder (↓ faster / ↑ slower / ≈ same)
- Arbitrary date-range query (`adctl stats range`) and per-reminder daily breakdown (`adctl stats app`)
- `adctl stats diagnose` for window-detection and database health checks

#### GUI dashboard
- Full PySide6 (Qt6) dark-themed window with sidebar navigation and five tabs: Reminders, Actions, Notes, Stats, Settings
- Per-tab keyboard shortcuts (Ctrl+N, Ctrl+E, Ctrl+D, Ctrl+R, Ctrl+S)
- Tab switching via Alt+1–5
- Daemon status indicator in the sidebar

#### CLI (`adctl`)
- Complete command surface for all features: daemon control, reminders, actions, notes, stats, GUI launch
- `adctl update` — clears stale bytecode and restarts the daemon; detects editable installs and skips redundant file sync
- `adctl uninstall` — interactive removal of package, entry points, systemd service, GNOME shortcuts, `.desktop` files, and legacy `automation-daemon` v1 artefacts
- ANSI-coloured output with `_ok` / `_err` / `_info` helpers

#### Internationalisation
- JSON-based i18n engine with fallback chain
- Four languages: English, French, Arabic (RTL), Russian
- Full right-to-left layout for Arabic (sidebar, forms, tables, dialogs)
- Language switchable from Settings at runtime; takes effect on GUI restart

#### Installation
- Single `install.sh` that detects distro (`dnf` / `apt` / `pacman` / `zypper`) and installs system dependencies automatically
- Optional GNOME keyboard shortcut registration (Ctrl+Shift+O for GUI, Ctrl+Shift+P for Quick Note)
- Primary support: Fedora 38+; tested on Ubuntu 22.04+, Debian 12+, Arch, openSUSE Tumbleweed
