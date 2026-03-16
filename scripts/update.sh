#!/usr/bin/env bash
# update.sh — PurposeOS in-place updater
#
# Run from anywhere — paths are resolved from the script location.
# Syncs all source files into the installed package directory in-place —
# faster than a full pip reinstall for code-only changes.
#
# When to use this:        When to use pip install instead:
#   code changes only        pyproject.toml changed (new dep / entry point)
#   i18n JSON changes        first install on a new machine
#   quick iteration          major structural changes

set -euo pipefail

BOLD='\033[1m'; CYAN='\033[36m'; GREEN='\033[32m'
YELLOW='\033[33m'; RED='\033[31m'; RESET='\033[0m'
info() { echo -e "${CYAN}→${RESET}  $*"; }
ok()   { echo -e "${GREEN}✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }
die()  { echo -e "${RED}✗${RESET}  $*" >&2; exit 1; }

# SCRIPT_DIR = scripts/  PROJECT_ROOT = the repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PKG_SRC="${PROJECT_ROOT}/purposeos"

# ── Verify source layout ───────────────────────────────────────────────────────
[[ -d "${PKG_SRC}" ]]                  || die "purposeos/ not found."
[[ -f "${PKG_SRC}/core/config.py" ]]   || die "purposeos/core/config.py not found."
[[ -f "${PKG_SRC}/i18n/__init__.py" ]] || die "purposeos/i18n/__init__.py not found."

# ── Resolve pip and python3 to the same interpreter ───────────────────────────
info "Resolving Python interpreter..."

PYTHON=""
for candidate in python3.13 python3.12 python3; do
    if command -v "${candidate}" &>/dev/null; then
        if "${candidate}" -c "import purposeos" &>/dev/null 2>&1; then
            PYTHON="${candidate}"
            break
        fi
    fi
done

if [[ -z "${PYTHON}" ]]; then
    PYTHON="python3"
fi

PIP="${PYTHON} -m pip"
ok "Using interpreter: $(command -v "${PYTHON}")  ($(${PYTHON} --version))"

# ── Locate installed package ───────────────────────────────────────────────────
info "Locating installed purposeos package..."
DEST=$(${PYTHON} -c \
    "import purposeos, os; print(os.path.dirname(purposeos.__file__))" \
    2>/dev/null) \
    || die "purposeos is not installed for ${PYTHON}. Run ./scripts/install.sh first."
ok "Installed at: ${DEST}"

# ── Detect editable install ────────────────────────────────────────────────────
updated=0
EDITABLE=false
if [[ "$(realpath "${DEST}")" == "$(realpath "${PKG_SRC}")" ]]; then
    EDITABLE=true
    ok "Editable install detected — source and install are the same directory."
    info "Skipping file sync (changes are already live)."
else
    # ── Sync Python source files ─────────────────────────────────────────────
    info "Syncing source files..."

    while IFS= read -r -d '' src_file; do
        rel="${src_file#"${PKG_SRC}"/}"
        dest_file="${DEST}/${rel}"
        dest_dir="$(dirname "${dest_file}")"

        if [[ ! -d "${dest_dir}" ]]; then
            mkdir -p "${dest_dir}"
            init="${dest_dir}/__init__.py"
            [[ -f "${init}" ]] || printf '"""purposeos sub-package."""\n' > "${init}"
        fi

        if [[ ! -f "${dest_file}" ]] || ! diff -q "${src_file}" "${dest_file}" &>/dev/null; then
            cp "${src_file}" "${dest_file}"
            echo -e "    ${GREEN}↑${RESET} ${rel}"
            (( updated++ )) || true
        else
            echo -e "    ${CYAN}=${RESET} ${rel}"
        fi
    done < <(find "${PKG_SRC}" \
        -not -path "*/__pycache__/*" \
        -not -name "*.pyc" \
        -name "*.py" \
        -print0 | sort -z)

    # ── Sync i18n JSON translation files ────────────────────────────────────
    info "Syncing i18n translation files..."
    I18N_SRC="${PKG_SRC}/i18n"
    I18N_DEST="${DEST}/i18n"
    mkdir -p "${I18N_DEST}"

    while IFS= read -r -d '' json_src; do
        fname="$(basename "${json_src}")"
        json_dest="${I18N_DEST}/${fname}"
        if [[ ! -f "${json_dest}" ]] || ! diff -q "${json_src}" "${json_dest}" &>/dev/null; then
            cp "${json_src}" "${json_dest}"
            echo -e "    ${GREEN}↑${RESET} i18n/${fname}"
            (( updated++ )) || true
        else
            echo -e "    ${CYAN}=${RESET} i18n/${fname}"
        fi
    done < <(find "${I18N_SRC}" -maxdepth 1 -name "*.json" -print0 | sort -z)
fi

# ── Always flush stale bytecode ────────────────────────────────────────────────
info "Clearing stale __pycache__..."
find "${PKG_SRC}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
if [[ "${EDITABLE}" == false ]]; then
    find "${DEST}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
fi
ok "__pycache__ cleared."

# ── Refresh manifest uninstall.sh ─────────────────────────────────────────────
MANIFEST_DIR="${HOME}/.local/share/purposeos"
MANIFEST_UNINSTALL="${MANIFEST_DIR}/uninstall.sh"
SRC_UNINSTALL="${SCRIPT_DIR}/uninstall.sh"

if [[ -d "${MANIFEST_DIR}" ]] && [[ -f "${SRC_UNINSTALL}" ]]; then
    if [[ ! -f "${MANIFEST_UNINSTALL}" ]] || \
       ! diff -q "${SRC_UNINSTALL}" "${MANIFEST_UNINSTALL}" &>/dev/null; then
        cp "${SRC_UNINSTALL}" "${MANIFEST_UNINSTALL}"
        chmod +x "${MANIFEST_UNINSTALL}"
        ok "Manifest uninstall.sh refreshed."
        (( updated++ )) || true
    fi
elif [[ ! -d "${MANIFEST_DIR}" ]]; then
    warn "Manifest directory not found — uninstall.sh not refreshed."
    warn "Re-run scripts/install.sh to recreate it."
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
if (( updated == 0 )); then
    ok "Everything already up to date."
else
    ok "${updated} file(s) updated."
fi

# ── Pip deps reminder ─────────────────────────────────────────────────────────
if [[ -f "${PROJECT_ROOT}/requirements.txt" ]]; then
    req_time=$(stat -c %Y "${PROJECT_ROOT}/requirements.txt" 2>/dev/null || echo 0)
    pkg_time=$(stat -c %Y "${DEST}/__init__.py"              2>/dev/null || echo 0)
    if (( req_time > pkg_time )); then
        echo ""
        warn "requirements.txt is newer than the installed package."
        warn "New dependencies may be missing. Run:"
        warn "  ${PIP} install --user -r ${PROJECT_ROOT}/requirements.txt"
    fi
fi

if [[ -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
    toml_time=$(stat -c %Y "${PROJECT_ROOT}/pyproject.toml" 2>/dev/null || echo 0)
    pkg_time=$(stat -c %Y "${DEST}/__init__.py"             2>/dev/null || echo 0)
    if (( toml_time > pkg_time )); then
        echo ""
        warn "pyproject.toml is newer than the installed package."
        warn "For entry point or dependency changes to take effect, run:"
        warn "  ${PIP} install --user ${PROJECT_ROOT}"
    fi
fi

# ── Unconditional daemon restart ───────────────────────────────────────────────
echo ""
info "Restarting daemon to load updated code..."
if systemctl --user is-active --quiet purposeos.service 2>/dev/null; then
    systemctl --user restart purposeos.service
    sleep 1
    if systemctl --user is-active --quiet purposeos.service; then
        ok "Daemon restarted successfully."
    else
        warn "Daemon failed to restart. Check logs: adctl logs"
    fi
else
    systemctl --user start purposeos.service 2>/dev/null || true
    sleep 1
    if systemctl --user is-active --quiet purposeos.service; then
        ok "Daemon started (was stopped before update)."
    else
        warn "Daemon is not running after update."
        warn "Start manually: adctl start   |   Check logs: adctl logs"
    fi
fi

echo ""
echo -e "${BOLD}${GREEN}Update complete.${RESET}"
echo "  adctl gui     — open the GUI"
echo "  adctl stats   — check stats from CLI"
echo "  adctl logs    — check for errors"
echo ""