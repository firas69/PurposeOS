# PurposeOS

[![CI](https://github.com/firas69/PurposeOS/actions/workflows/ci.yml/badge.svg)](https://github.com/firas69/PurposeOS/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/firas69/PurposeOS/branch/main/graph/badge.svg)](https://codecov.io/gh/firas69/PurposeOS)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**A Linux desktop automation daemon.** Set reminders, schedule actions, capture quick notes, and start building awareness of how you actually spend your attention — all from a clean GUI or the terminal.

Built for Fedora (GNOME/Wayland), compatible with Ubuntu, Arch, and openSUSE.

---

## Features

- **Reminders** — Screen-wide overlays or standard notifications, triggered at a fixed time, on a repeating interval, weekly, or on boot
- **Actions** — Automatically open files, launch apps, run commands, or open URLs on a schedule
- **Quick Note** — A floating window (Ctrl+Shift+P) for capturing thoughts without leaving what you're doing
- **Notes Manager** — Browse, view, edit, and delete all saved notes from the GUI
- **Stats** — Track how quickly you respond to your own reminders, week over week. A small but honest signal: the faster you respond, the less friction there is between your intentions and your attention
- **Multi-language GUI** — English, French, Arabic (RTL), and Russian; switchable from Settings
- **Dark GUI** — Full PySide6 dashboard with sidebar navigation and per-section keyboard shortcuts
- **systemd integration** — Runs as a user service, starts on login, restarts on failure

---


## Installation

```bash
git clone https://github.com/firas69/purposeos.git
cd purposeos
chmod +x scripts/install.sh
./scripts/install.sh
```

The installer detects your distro (`dnf` / `apt` / `pacman` / `zypper`) and installs system dependencies automatically. At the end it offers to register optional GNOME keyboard shortcuts.

**Requirements:** Python 3.10+, PySide6, a running GNOME/Wayland or X11 session.

---

## Quick Start

```bash
adctl status                                            # is the daemon running?
adctl reminders add --message "Stand up" --at 11:00    # daily at 11:00
adctl reminders add --message "Drink water" --every 60 # every 60 minutes
adctl actions add --type open_file --target ~/todo.txt --at 09:00
adctl gui                                               # open the dashboard
adctl quicknote                                         # floating note window
```

---

## CLI Reference

### Daemon control

| Command | Description |
|---|---|
| `adctl start` | Start the daemon |
| `adctl stop` | Stop the daemon |
| `adctl restart` | Restart the daemon |
| `adctl reload` | Live-reload config without restart |
| `adctl status` | Show running status |
| `adctl logs [-n N]` | Tail the daemon log (default 50 lines) |
| `adctl enable` | Enable autostart at login |
| `adctl disable` | Disable autostart |

### Reminders

```bash
adctl reminders list
adctl reminders add --message "TEXT" --at HH:MM [--title NAME] [--urgency low|normal|critical]
adctl reminders add --message "TEXT" --every MINUTES
adctl reminders add --message "TEXT" --day mon|tue|wed|thu|fri|sat|sun
adctl reminders remove N
adctl reminders enable N
adctl reminders disable N
```

### Actions

```bash
adctl actions list
adctl actions add --type open_file    --target ~/path/to/file.txt --at 09:00
adctl actions add --type open_app     --target firefox --at 08:55
adctl actions add --type run_command  --target "notify-send hello" --every 60
adctl actions add --type open_url     --target https://example.com --at 08:00
adctl actions add --type show_notification --at 10:00
adctl actions remove N
adctl actions enable N
adctl actions disable N
```

### Notes

```bash
adctl notes new          # open terminal editor
adctl notes list         # list saved notes
adctl notes show N       # print note to terminal
adctl notes edit N       # edit in terminal
adctl notes delete N     # delete
adctl quicknote          # floating GUI window (Ctrl+Shift+P)
adctl gui --notes        # open GUI on the Notes tab
```

### Stats

```bash
adctl stats              # reminder response times today
adctl stats week         # this week vs last week, per reminder
adctl stats range 2025-01-01 2025-01-31  # arbitrary date range
adctl stats notifications # alias for stats week
adctl stats app "Stand up" --days 14     # per-reminder daily breakdown
adctl stats diagnose     # test window detection + DB status
```

### Package management

| Command | Description |
|---|---|
| `adctl update` | Sync source changes into the installed package in-place |
| `adctl uninstall` | Interactively remove PurposeOS |
| `adctl version` | Show the installed version |

---

## GUI

Open with `adctl gui` or Ctrl+Shift+O.

| Tab | Shortcuts | What it does |
|---|---|---|
| Reminders | Ctrl+N Add, Ctrl+E Edit, Ctrl+D Delete | Manage scheduled reminders |
| Actions | Ctrl+N Add, Ctrl+E Edit, Ctrl+D Delete | Manage scheduled actions |
| Notes | Ctrl+N New, Ctrl+V View, Ctrl+E Edit, Ctrl+D Delete | Browse and edit notes |
| Stats | Ctrl+R Refresh | Reminder response times and weekly trend |
| Settings | Ctrl+S Save | Log level, timeout, notes folder, language |

Switch between tabs with **Alt+1** through **Alt+5**.

---

## Stats

PurposeOS tracks one thing in the stats module right now: **how quickly you respond to your own reminders**.

Every time you click Done on a notification, the response time (seconds from the notification appearing to you clicking Done) is recorded. The stats view surfaces this as a per-reminder weekly average, compared against the previous week.

```
REMINDER RESPONSE TIMES — THIS WEEK
──────────────────────────────────────
Reminder          Avg       Count      
──────────────────────────────────────
Morning check     4s        12      
Drink water       18s       8       
Focus block       32s       5       
```

This is intentionally minimal. A fast response doesn't prove deep focus, and a slow one doesn't prove distraction — but the trend over time is harder to game than a click count. If your "Stand up" reminder consistently takes 40 seconds to acknowledge, that's information.

The data collected here — per-interaction timestamps, response times, and action types — is also the foundation for more granular focus metrics down the line: streak tracking, time-of-day patterns, correlation between reminder types and response latency. None of that is implemented yet, but the schema is already capturing what's needed.

---

## Language Support

PurposeOS supports English, French, Arabic, and Russian. Change language in **Settings → Language**, then restart the GUI.

Arabic enables full right-to-left (RTL) layout — sidebar, forms, tables, and dialogs all mirror automatically.

### Translation key namespaces

All UI strings are organised in nested JSON files under `purposeos/i18n/`. The key namespaces are:

| Namespace | Covers |
|---|---|
| `app.*` | Application name and window title |
| `navigation.*` | Sidebar section names, keyboard shortcuts guide |
| `reminders.*` | Reminders section: buttons, table headers, form fields, dialogs |
| `actions.*` | Actions section: buttons, table headers, form fields, status strings |
| `notes.*` | Notes section: buttons, table headers, dialogs, char counter |
| `stats.*` | Stats section: headings, empty states, trend labels |
| `settings.*` | Settings section: form labels, save button |
| `status.*` | Daemon status indicator |
| `dialogs.*` | Language-changed dialog |
| `trigger.*` | Trigger type descriptions (On boot, Daily at, Every N min, Weekly) |
| `common.*` | Shared strings: Yes/No, min, sec, path warnings |

### Using translations in new code

```python
from purposeos.i18n import t, set_language, get_language, get_all_languages, is_rtl

# Get a translated string (second arg is the fallback if key is missing)
title = t("reminders.dialog.add_title", "Add Reminder")

# Switch language
set_language("fr")

# Check available languages
langs = get_all_languages()  # {"en": "English", "fr": "Français", ...}

# RTL-aware widget layout
from PySide6.QtCore import Qt
if is_rtl():
    widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
```

### Adding a new language

1. Create `purposeos/i18n/<code>.json` with the same nested structure as `en.json`
2. If the language reads right-to-left, add its code to `RTL_LANGUAGES` in `purposeos/i18n/__init__.py`
3. Run `adctl update` — the new language appears in Settings → Language immediately

---

## Configuration

Config file: `~/.config/automation-daemon/config.yaml`

The daemon reloads this file automatically on save. Trigger a manual reload with `adctl reload`.

```yaml
settings:
  log_level: INFO                   # DEBUG | INFO | WARNING | ERROR
  notification_timeout_ms: 30000    # auto-close for screen-wide overlays (ms)
  screen_wide_default: true
  tracker_poll_interval_sec: 5
  notes_dir: ""                     # custom notes folder (empty = default)
  language: en                      # en | fr | ar | ru

reminders:
  - title: "Morning Check-in"
    message: "Review your task list."
    trigger: daily
    trigger_value: "09:00"
    urgency: normal
    screen_wide: true
    auto_close_sec: 30
    enabled: true

  - title: "Hydration"
    message: "Drink a glass of water."
    trigger: interval_minutes
    trigger_value: 60
    enabled: true

actions:
  - action_type: open_file
    trigger: boot
    target: ~/Documents/todo.txt
    enabled: true
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+Shift+P | Open Quick Note floating window |
| Ctrl+Shift+O | Open full PurposeOS GUI |

Register at install time, or manually at any point:

```bash
./scripts/set_notes_shortcut.sh            # Ctrl+Shift+P
./scripts/set_gui_shortcut.sh              # Ctrl+Shift+O

# Custom binding:
./scripts/set_notes_shortcut.sh '<Super>n'
./scripts/set_gui_shortcut.sh '<Super>o'
```

Shortcuts use `gsettings` and require GNOME (Wayland or X11).

---

## File Layout

### Runtime directories

```
~/.config/automation-daemon/
├── config.yaml          # reminders, actions, settings
└── notes/               # plain .txt note files (or custom path)

~/.local/share/automation-daemon/
├── tracker.db           # SQLite: app sessions + notification interactions
└── logs/
    └── daemon.log

~/.local/share/purposeos/
├── uninstall.sh         # used by `adctl uninstall`
└── source_path          # project root path, used by `adctl update`

~/.config/systemd/user/
└── purposeos.service

~/.local/bin/
├── adctl
└── purposeos-daemon
```

### Source tree

```
PurposeOS/
├── purposeos/                      # Python package (source)
│   ├── adctl.py                    # CLI entry point (delegates to cli/)
│   ├── main.py                     # Daemon entry point
│   ├── __init__.py
│   ├── __main__.py
│   │
│   ├── core/
│   │   └── config.py               # Dataclasses, YAML I/O, path constants
│   │
│   ├── daemon/
│   │   ├── scheduler.py            # APScheduler setup, trigger factory
│   │   ├── actions.py              # Action executors (open file/app/url/cmd)
│   │   └── watcher.py              # Config file inotify watcher
│   │
│   ├── data/
│   │   ├── stats.py                # Terminal stats output (response times + trends)
│   │   └── tracker/
│   │       ├── db.py               # SQLite schema, migrations, session I/O
│   │       ├── detection.py        # Window detection (D-Bus → wnck → xdotool)
│   │       └── tracker.py          # AppTrackerThread
│   │
│   ├── notifications/
│   │   ├── notifications.py        # Orchestration (fire_reminder, overlay launch)
│   │   ├── interactions.py         # DB recording of notification interactions
│   │   └── sound.py                # ffmpeg → paplay audio pipeline
│   │
│   ├── notes/
│   │   ├── storage.py              # File I/O (list, read, save, delete)
│   │   ├── editor.py               # Curses terminal editor
│   │   └── cli.py                  # ANSI-formatted output for adctl notes
│   │
│   ├── ui/
│   │   └── overlay.py              # Fullscreen GTK4 notification overlay
│   │
│   ├── gui/
│   │   ├── main.py                 # PurposeOSWindow + main() entry point
│   │   ├── quicknote.py            # Floating quick-note window
│   │   ├── _style.py               # Qt stylesheet constant
│   │   ├── _helpers.py             # t(), is_rtl(), _apply_rtl(), shortcuts, i18n
│   │   ├── _config_bridge.py       # GUI-side config read/write, daemon reload
│   │   ├── dialogs/
│   │   │   ├── reminder.py         # Add/Edit Reminder dialog
│   │   │   ├── action.py           # Add/Edit Action dialog + type utilities
│   │   │   └── note.py             # Note viewer/editor dialog
│   │   └── widgets/
│   │       └── stats_chart.py      # Reserved for future chart widgets
│   │
│   ├── cli/
│   │   ├── parser.py               # Argument parser, _COMMAND_MAP, main()
│   │   ├── daemon_cmds.py          # start/stop/restart/reload/status/logs/enable/disable
│   │   ├── reminder_cmds.py        # reminders list/add/remove/enable/disable
│   │   ├── action_cmds.py          # actions list/add/remove/enable/disable
│   │   ├── stats_cmds.py           # stats today/week/range/notifications/app/diagnose
│   │   ├── notes_cmds.py           # notes list/new/edit/show/delete
│   │   ├── gui_cmds.py             # gui, quicknote
│   │   ├── meta_cmds.py            # update, uninstall, version
│   │   ├── _config_io.py           # _load_cfg_safe, _save_cfg_safe
│   │   └── _output.py              # ANSI colours, _ok/_err/_info
│   │
│   └── i18n/
│       ├── __init__.py             # t(), set_language(), is_rtl(), fallback chain
│       ├── en.json
│       ├── fr.json
│       ├── ar.json
│       └── ru.json
│
├── scripts/                        # Install and maintenance shell scripts
│   ├── install.sh                  # Distro-aware installer
│   ├── uninstall.sh                # Full removal including legacy v1 artefacts
│   ├── update.sh                   # In-place updater (editable-install aware)
│   ├── set_gui_shortcut.sh         # Register Ctrl+Shift+O in GNOME
│   ├── set_notes_shortcut.sh       # Register Ctrl+Shift+P in GNOME
│   └── purposeos.service           # systemd user service unit
│
├── tests/
│   ├── test_adctl.py
│   ├── test_config_i18n.py
│   └── test_scheduler.py
│
├── docs/                           # Screenshots and demo assets
├── .github/workflows/ci.yml        # GitHub Actions (test + shellcheck)
├── .gitignore
├── conftest.py                     # pytest sys.path setup
├── pyproject.toml                  # build config, ruff, mypy, pytest, coverage
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── DEVELOPMENT.md
```

---

## Updating

After pulling new changes from the source tree:

```bash
adctl update
```

This clears stale bytecode and restarts the daemon. For editable installs (`pip install -e .`) the file sync is skipped since changes are already live — bytecode clearing and daemon restart are the only steps that matter.

If `pyproject.toml` changed (new dependency or entry point), do a full reinstall instead:

```bash
pip install --user -e .
```

---

## Uninstalling

```bash
adctl uninstall
```

Stops the daemon, removes the package, entry points, systemd service, GNOME shortcuts, and `.desktop` files. Also cleans up legacy `automation-daemon` v1 artefacts if present. Prompts before deleting config, notes, and the database.

---

## Development

```bash
# Install with test dependencies
pip install --user -e ".[test]"

# Run the full test suite
pytest

# Run a specific file
pytest tests/test_scheduler.py -v

# Run a single test
pytest tests/test_adctl.py::test_reminders_add -v
```

Tests live in `tests/`. `conftest.py` at the project root handles `sys.path` so `import purposeos` always resolves to the local source tree.

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture details, extension points, and commit style.
See [DEVELOPMENT.md](DEVELOPMENT.md) for CI setup, release tagging, and coverage configuration.

### Import rules

The sub-packages have a strict one-way dependency chain. Never import upward:

```
core / i18n           ← import nothing from purposeos
notes / data          ← import core only
daemon                ← import core, data, notifications
notifications         ← import core only  (never gui, never daemon)
cli                   ← import core, data, notes, daemon  (gui lazily only)
gui                   ← import core, i18n, notes  (never daemon, never cli)
```

---

## Distro Support

| Distro | Package Manager | Status |
|---|---|---|
| Fedora 38+ | dnf | Primary |
| RHEL / CentOS Stream | dnf | Supported |
| Ubuntu 22.04+ | apt | Supported |
| Debian 12+ | apt | Supported |
| Linux Mint | apt | Supported |
| Arch / Manjaro | pacman | Supported |
| openSUSE Tumbleweed | zypper | Supported |

---

## Tech Stack

| Component | Technology |
|---|---|
| Daemon / scheduler | Python 3, APScheduler |
| GUI | PySide6 (Qt6) |
| Notifications | libnotify / notify2 |
| Screen-wide overlays | GTK4 (PyGObject) |
| App tracking | GNOME D-Bus → wnck → xdotool fallback chain |
| Config | YAML (PyYAML), inotify watcher |
| Database | SQLite |
| Internationalisation | Custom pure-Python JSON-based i18n, 4 languages |
| Service management | systemd user units |

---

## License

MIT
