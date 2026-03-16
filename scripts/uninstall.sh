#!/usr/bin/env bash
# uninstall.sh — PurposeOS v2 Uninstaller
#
# Removes all traces of PurposeOS and the legacy automation-daemon v1.
# Run as your normal user (NOT root).

set -euo pipefail

CYAN='\033[36m'; GREEN='\033[32m'; YELLOW='\033[33m'
RED='\033[31m'; RESET='\033[0m'; BOLD='\033[1m'
info() { echo -e "${CYAN}→${RESET}  $*"; }
ok()   { echo -e "${GREEN}✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }

echo ""
echo -e "${BOLD}${RED}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${RED}║   PurposeOS v2 — Uninstaller         ║${RESET}"
echo -e "${BOLD}${RED}╚══════════════════════════════════════╝${RESET}"
echo ""
warn "This will remove the PurposeOS daemon, package, entry points,"
warn "systemd services, GNOME shortcuts, and .desktop files."
warn "Legacy automation-daemon v1 files will also be cleaned up."
echo ""
printf "  Continue? [y/N]: "
read -r confirm
[[ "${confirm,,}" == "y" ]] || { echo "Aborted."; exit 0; }
echo ""

# ── 1. Stop and disable all related services ───────────────────────────────────
info "Stopping services..."
for svc in purposeos.service automation-daemon.service; do
    systemctl --user stop    "${svc}" 2>/dev/null && ok "Stopped ${svc}"   || true
    systemctl --user disable "${svc}" 2>/dev/null && ok "Disabled ${svc}"  || true
done
systemctl --user daemon-reload

# ── 2. Kill any lingering daemon processes ─────────────────────────────────────
info "Killing any lingering daemon processes..."
pkill -f "purposeos.main"    2>/dev/null || true
pkill -f "purposeos-daemon"  2>/dev/null || true
pkill -f "automation.daemon" 2>/dev/null || true
pkill -f "automation-daemon" 2>/dev/null || true
ok "Processes cleared."

# ── 3. Remove systemd service files ───────────────────────────────────────────
info "Removing systemd service files..."
SYSTEMD_DIR="${HOME}/.config/systemd/user"
for svc_file in purposeos.service automation-daemon.service; do
    if [[ -f "${SYSTEMD_DIR}/${svc_file}" ]]; then
        rm -f "${SYSTEMD_DIR}/${svc_file}"
        ok "Removed ${SYSTEMD_DIR}/${svc_file}"
    fi
done
systemctl --user daemon-reload

# ── 4. Remove GNOME keyboard shortcuts ────────────────────────────────────────
if command -v gsettings &>/dev/null; then
    info "Removing GNOME keyboard shortcuts..."
    SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
    KEY="custom-keybindings"
    existing=$(gsettings get "${SCHEMA}" "${KEY}" 2>/dev/null || echo "@as []")
    existing_clean=$(echo "${existing}" | tr -d "[]' " | tr ',' '\n' | grep -v '^$' || true)
    new_list_items=()
    removed=0
    for slot in ${existing_clean}; do
        slot_name=$(gsettings get "${SCHEMA}.custom-keybinding:${slot}" name \
            2>/dev/null | tr -d "'" || true)
        if [[ "${slot_name}" == "PurposeOS Notes"      ||
              "${slot_name}" == "PurposeOS GUI"         ||
              "${slot_name}" == "PurposeOS Quick Note" ]]; then
            gsettings reset "${SCHEMA}.custom-keybinding:${slot}" name    2>/dev/null || true
            gsettings reset "${SCHEMA}.custom-keybinding:${slot}" command 2>/dev/null || true
            gsettings reset "${SCHEMA}.custom-keybinding:${slot}" binding 2>/dev/null || true
            ok "Removed shortcut: ${slot_name}"
            (( removed++ )) || true
        else
            new_list_items+=("'${slot}'")
        fi
    done
    if (( removed > 0 )); then
        if (( ${#new_list_items[@]} == 0 )); then
            gsettings set "${SCHEMA}" "${KEY}" "@as []"
        else
            IFS=','; gsettings set "${SCHEMA}" "${KEY}" "[${new_list_items[*]}]"; unset IFS
        fi
        ok "${removed} keyboard shortcut(s) removed."
    else
        info "No PurposeOS keyboard shortcuts found."
    fi
else
    info "gsettings not available — skipping shortcut cleanup."
fi

# ── 5. Remove entry-point scripts ─────────────────────────────────────────────
info "Removing entry-point scripts..."
LOCAL_BIN="${HOME}/.local/bin"
for bin in adctl purposeos-daemon automation-daemon; do
    if [[ -f "${LOCAL_BIN}/${bin}" ]]; then
        rm -f "${LOCAL_BIN}/${bin}"
        ok "Removed ${LOCAL_BIN}/${bin}"
    fi
done

# ── 6. Uninstall Python packages ──────────────────────────────────────────────
info "Uninstalling Python packages..."
pip uninstall -y purposeos         2>/dev/null && ok "Removed purposeos pip package."         || true
pip uninstall -y automation-daemon 2>/dev/null && ok "Removed automation-daemon pip package." || true

# Remove any lingering dist-info / egg-link from user site-packages
SITE=$(python3 -c "import site; print(site.getusersitepackages())" 2>/dev/null || true)
if [[ -n "${SITE}" ]]; then
    info "Cleaning site-packages at ${SITE}..."
    rm -rf "${SITE}/purposeos"*
    rm -rf "${SITE}/automation_daemon"*
    rm -rf "${SITE}/automation-daemon"*
    ok "site-packages cleaned."
fi

# ── 7. Remove .desktop files ──────────────────────────────────────────────────
info "Removing .desktop files..."
APPS_DIR="${HOME}/.local/share/applications"
removed_desktop=0
for desktop in purposeos-quicknote.desktop purposeos-gui.desktop purposeos-notes.desktop; do
    if [[ -f "${APPS_DIR}/${desktop}" ]]; then
        rm -f "${APPS_DIR}/${desktop}"
        ok "Removed ${desktop}"
        (( removed_desktop++ )) || true
    fi
done
(( removed_desktop > 0 )) && update-desktop-database "${APPS_DIR}" 2>/dev/null || true

# ── 8. Remove leftover runtime files ──────────────────────────────────────────
info "Removing runtime temp files..."
rm -f /tmp/purposeos_overlay_*.json
rm -f /tmp/automation_daemon*.pid
ok "Runtime files cleared."

# ── 9. Optional: remove config, notes, and database ──────────────────────────
CONFIG_DIR="${HOME}/.config/automation-daemon"
DATA_DIR="${HOME}/.local/share/automation-daemon"

echo ""
echo -e "${BOLD}── Optional: remove user data ──────────────────────────────────${RESET}"
echo ""

if [[ -d "${CONFIG_DIR}" ]]; then
    note_count=$(find "${CONFIG_DIR}/notes" -name "*.txt" 2>/dev/null | wc -l || echo 0)
    echo -e "  Config & notes: ${CONFIG_DIR}"
    echo -e "  Contains ${note_count} note(s)."
    printf "  Delete config and all notes? [y/N]: "
    read -r del_config
    if [[ "${del_config,,}" == "y" ]]; then
        rm -rf "${CONFIG_DIR}"
        ok "Removed ${CONFIG_DIR}"
    else
        info "Config and notes kept."
    fi
else
    info "Config directory not found."
fi

if [[ -d "${DATA_DIR}" ]]; then
    db_size=$(du -sh "${DATA_DIR}" 2>/dev/null | cut -f1 || echo "?")
    echo ""
    echo -e "  Stats database & logs: ${DATA_DIR}  (${db_size})"
    printf "  Delete database and logs? [y/N]: "
    read -r del_data
    if [[ "${del_data,,}" == "y" ]]; then
        rm -rf "${DATA_DIR}"
        ok "Removed ${DATA_DIR}"
    else
        info "Database and logs kept."
    fi
else
    info "Data directory not found."
fi

# ── 10. Remove manifest directory ─────────────────────────────────────────────
MANIFEST_DIR="${HOME}/.local/share/purposeos"
if [[ -d "${MANIFEST_DIR}" ]]; then
    rm -rf "${MANIFEST_DIR}"
    ok "Removed manifest directory ${MANIFEST_DIR}"
fi

# ── 11. PATH reminder ─────────────────────────────────────────────────────────
echo ""
if grep -qE 'export PATH.*\.local/bin' "${HOME}/.bashrc" 2>/dev/null || \
   grep -qE 'export PATH.*\.local/bin' "${HOME}/.zshrc"  2>/dev/null; then
    warn "$HOME/.local/bin is still in your PATH via .bashrc or .zshrc."
    warn "If you no longer need it, remove the export line manually."
fi

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║   PurposeOS v2 uninstalled.          ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════╝${RESET}"
echo ""
echo "Run ./install.sh to do a fresh install."
echo ""