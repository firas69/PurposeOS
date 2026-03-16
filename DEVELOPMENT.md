# Development Guide

Practical setup notes for CI, coverage, releases, and commit hygiene.
Architecture and extension points live in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## CI (GitHub Actions)

The workflow at `.github/workflows/ci.yml` runs on every push and pull request to `main`.

**Jobs:**
- `test` — runs the full pytest suite across Python 3.10, 3.11, 3.12, and 3.13
- `lint-shell` — runs `shellcheck` against all scripts in `scripts/*.sh`

**Non-blocking steps** (annotate but don't fail the build):
- `ruff check` — linter
- `ruff format --check` — formatter
- `mypy` — type checker
- `shellcheck` — shell script analysis

Only `pytest` and the coverage threshold are blocking. This lets CI stay green while the codebase is progressively cleaned up.

The CI badge in the README goes live automatically on the first push after the workflow file exists.

---

## Codecov setup (one-time)

1. Go to [codecov.io](https://codecov.io) and sign in with GitHub
2. Add the `firas69/PurposeOS` repository
3. Copy the upload token
4. In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CODECOV_TOKEN`
   - Value: your token
5. The CI workflow uploads coverage after the first successful run on Python 3.13

The coverage badge in the README goes live after that first upload.

---

## Tagging a release

```bash
# Tag the current commit
git tag -a v1.0.0 -m "PurposeOS v1.0.0 — initial release"
git push origin v1.0.0
```

Then on GitHub:
- Go to **Releases → Draft a new release**
- Choose tag `v1.0.0`
- Title: `v1.0.0 — Initial release`
- Body: paste the `[1.0.0]` section from `CHANGELOG.md`
- Publish release

---

## Capturing demo assets

```bash
mkdir -p docs
```

**Terminal GIF** (requires `asciinema` and `agg`):

```bash
# Record
asciinema rec /tmp/demo.cast

# Run these during recording:
adctl status
adctl reminders list
adctl reminders add --message "Stand up" --at 11:00
adctl stats week

# Stop: Ctrl+D

# Install agg: cargo install agg
agg /tmp/demo.cast docs/demo-cli.gif
```

**GUI screenshot:**

```bash
adctl gui &
gnome-screenshot -w -f docs/screenshot-dashboard.png
```

---

## Commit hygiene

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

| Type | When to use |
|---|---|
| `feat` | New feature visible to users |
| `fix` | Bug fix |
| `refactor` | Code change with no feature or bug impact |
| `docs` | README, CHANGELOG, CONTRIBUTING, docstrings |
| `test` | Adding or improving tests |
| `chore` | CI, build tooling, dependency bumps |
| `style` | Formatting only (ruff fmt, no logic change) |

**Scopes:** `daemon`, `cli`, `gui`, `notifications`, `notes`, `stats`, `i18n`, `core`, `install`

**Examples:**

```bash
git commit -m "feat(daemon): add on-idle trigger type via xprintidle"
git commit -m "fix(notifications): skip overlay launch when session is locked"
git commit -m "docs: add Codecov badge and demo section"
git commit -m "test(scheduler): cover weekly trigger with DST boundary"
git commit -m "chore(ci): add Python 3.13 to CI matrix"
```

**One logical change = one commit.** Stage only the files relevant to the change before committing:

```bash
git add purposeos/daemon/scheduler.py purposeos/core/config.py
git commit -m "feat(daemon): add on-idle trigger type via xprintidle"
```

---

## Rewriting history (optional, solo projects only)

Safe to do before the repo gets external collaborators or public attention.

```bash
# Interactively rebase all commits from the beginning
git rebase -i --root

# In the editor:
#   reword  — rename a commit message
#   squash  — fold a commit into the one above it
#   drop    — remove a commit entirely

# Force-push the cleaned history
git push origin main --force-with-lease
```

Do **not** do this after sharing the URL publicly or adding collaborators.

---

## Raising coverage over time

The current threshold in `pyproject.toml` is `fail_under = 35`. Raise it in small increments as tests are added:

```toml
[tool.coverage.report]
fail_under = 50   # raise from 35 as daemon/notes/stats tests are added
```

Current coverage breakdown:
- Well covered (>85%): `core/config.py`, `i18n/`, `cli/` (most modules)
- Partially covered: `daemon/scheduler.py`, `notifications/`
- Excluded from measurement: `purposeos/ui/*`, `purposeos/gui/*` (require a display server)

Focus coverage efforts on `data/stats.py`, `daemon/actions.py`, and `notifications/` — these have the most logic and the lowest current coverage.
