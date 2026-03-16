# Contributing to PurposeOS

Thanks for your interest. This document covers how to set up a development environment, the internal architecture, and the main extension points — adding a trigger type, an action type, a new stat, or a new language.

---

## Development setup

```bash
git clone https://github.com/firas69/purposeos.git
cd purposeos

# Install in editable mode with test dependencies
pip install --user -e ".[test]"

# Verify the CLI is available
adctl version
```

**Requirements:** Python 3.10+, a running GNOME/Wayland or X11 session, and the system packages installed by `install.sh` (PySide6, PyGObject, libnotify).

---

## Running the tests

```bash
# Full suite
pytest

# With coverage report
pytest --cov=purposeos --cov-report=term-missing

# Single file
pytest tests/test_scheduler.py -v

# Single test
pytest tests/test_adctl.py::test_reminders_add -v
```

`conftest.py` at the project root patches `sys.path` so `import purposeos` always resolves to the local source tree, regardless of any installed version.

---

## Import rules

The sub-packages have a strict one-way dependency chain. **Never import upward.**

```
core / i18n          ← import nothing from purposeos
notes / data         ← import core only
daemon               ← import core, data, notifications
notifications        ← import core only  (never gui, never daemon)
cli                  ← import core, data, notes, daemon  (gui lazily only)
gui                  ← import core, i18n, notes  (never daemon, never cli)
```

Violating this chain introduces circular imports and couples layers that are intentionally isolated.

---

## Adding a new trigger type

Trigger types control *when* a reminder or action fires.

**1. `purposeos/core/config.py`**
Add the new trigger name to the `TriggerType` string literal or enum. Add any new fields to the `Reminder` and `Action` dataclasses if the trigger needs extra config keys.

**2. `purposeos/daemon/scheduler.py`**
Add a branch in the trigger factory function that maps a `TriggerType` to an APScheduler trigger. APScheduler supports cron, interval, date, and custom triggers — see [APScheduler docs](https://apscheduler.readthedocs.io/).

**3. `purposeos/cli/reminder_cmds.py` and `purposeos/cli/action_cmds.py`**
Add the new trigger flag to the `add` subparser (e.g. `--on-idle`). Handle it alongside the existing `--at`, `--every`, and `--day` branches.

**4. `purposeos/i18n/en.json`** (and other language files)
Add a human-readable label under the `trigger.*` namespace:
```json
"trigger": {
  "on_idle": "After idle for N minutes"
}
```

**5. GUI dialog (`purposeos/gui/dialogs/reminder.py`)**
Add the new option to the trigger-type combo box and show/hide the relevant input fields.

---

## Adding a new action type

Action types control *what happens* when a scheduled action fires.

**1. `purposeos/daemon/actions.py`**
Add a new executor function and register it in the dispatcher dictionary:
```python
def _run_my_action(target: str) -> None:
    ...

_EXECUTORS = {
    ...
    "my_action": _run_my_action,
}
```

**2. `purposeos/core/config.py`**
Add the new type name to the `ActionType` literal/enum.

**3. `purposeos/cli/action_cmds.py`**
Add the type to the `--type` choices list and document any special `--target` format in the help string.

**4. GUI dialog (`purposeos/gui/dialogs/action.py`)**
Add the type to the combo box and update the target-field label/placeholder to match.

---

## Extending the Stats module

Stats are driven by two tables in `tracker.db`:

- `app_sessions` — one row per daemon-launched app/file (`is_daemon_launch = 1`)
- `notification_interactions` — one row per notification interaction, including `response_sec` (seconds from display to Done click) and `action` (`done` / `dismissed` / `pending`)

**Adding a new CLI stat:**

1. Add a query function to `purposeos/data/stats.py`. Follow the existing pattern — return a formatted string, use `_connect(db_path)` for the connection.
2. Add a subcommand branch in `purposeos/cli/stats_cmds.py`.
3. Register the subcommand in `purposeos/cli/parser.py`.

**Adding a new GUI stat card:**

All stat cards are rendered inside `_refresh_stats()` in `purposeos/gui/main.py`. Add your query inline (or import from `stats.py`) and append a new `QFrame` card to `self._stats_inner`. Follow the existing card layout: `QHBoxLayout` with a name label, a value label, and an optional trend label.

The `response_sec` column is the current primary signal. Future metrics to build on include:
- Interaction streaks (consecutive days with at least one Done click)
- Time-of-day response patterns (hour bucketing on `shown_at`)
- Per-reminder response-time percentiles

---

## Adding a new language

1. Copy `purposeos/i18n/en.json` to `purposeos/i18n/<code>.json` (e.g. `de.json` for German).
2. Translate all string values. Keep the JSON key structure identical — the fallback chain silently falls back to English for any missing key, so partial translations work.
3. If the language reads right-to-left, add its code to `RTL_LANGUAGES` in `purposeos/i18n/__init__.py`.
4. Run `adctl update` — the new language appears immediately in Settings → Language.

### Translation key namespaces

| Namespace | Covers |
|---|---|
| `app.*` | Application name and window title |
| `navigation.*` | Sidebar section names, keyboard shortcuts guide |
| `reminders.*` | Reminders section: buttons, table headers, form fields, dialogs |
| `actions.*` | Actions section: buttons, table headers, form fields, status strings |
| `notes.*` | Notes section: buttons, dialogs, char counter |
| `stats.*` | Stats section: headings, empty states, trend labels |
| `settings.*` | Settings section: form labels, save button |
| `trigger.*` | Trigger type human-readable descriptions |
| `common.*` | Shared strings: Yes/No, min, sec, path warnings |

---

## Commit message style

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short description>

[optional body]
```

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`
**Scopes:** `daemon`, `cli`, `gui`, `notifications`, `notes`, `stats`, `i18n`, `core`, `install`

Examples:
```
feat(daemon): add on-idle trigger type via xprintidle
fix(notifications): skip overlay launch when session is locked
docs(i18n): document RTL_LANGUAGES registration step
test(scheduler): cover weekly trigger with DST boundary
chore(ci): add Python 3.13 to CI matrix
```

---

## Reporting bugs

Open an issue with:
- Your distro and desktop environment
- Output of `adctl status` and `adctl logs -n 30`
- Output of `adctl stats diagnose` if the issue involves notifications or window detection
- Steps to reproduce
