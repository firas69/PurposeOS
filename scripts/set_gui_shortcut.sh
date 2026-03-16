#!/usr/bin/env bash
# set_gui_shortcut.sh — Register Ctrl+Shift+O as a GNOME keyboard shortcut
# that opens the PurposeOS main GUI window from anywhere on the desktop.
#
# Run once after install. Re-run to change the key binding.
# Works on GNOME 40+ (Fedora 34+).

set -euo pipefail

CYAN='\033[36m'; GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; RESET='\033[0m'
info() { echo -e "${CYAN}→${RESET}  $*"; }
ok()   { echo -e "${GREEN}✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }
die()  { echo -e "${RED}✗${RESET}  $*" >&2; exit 1; }

command -v gsettings &>/dev/null || die "gsettings not found. Are you running GNOME?"
info "Desktop: ${XDG_CURRENT_DESKTOP:-unknown}"

# GNOME custom shortcuts run with a stripped PATH (/usr/bin:/bin only),
# so ~/.local/bin is invisible. We must use the full absolute path to adctl.
ADCTL_PATH=""
for candidate in \
    "${HOME}/.local/bin/adctl" \
    "/usr/local/bin/adctl" \
    "$(command -v adctl 2>/dev/null || true)"
do
    if [[ -x "${candidate}" ]]; then
        ADCTL_PATH="${candidate}"
        break
    fi
done
[[ -n "${ADCTL_PATH}" ]] || die "adctl not found. Run ./install.sh first."
ok "Found adctl at: ${ADCTL_PATH}"

BINDING="${1:-<Primary><Shift>o}"
NAME="PurposeOS GUI"
COMMAND="${ADCTL_PATH} gui"
SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
KEY="custom-keybindings"
SLOT_BASE="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

existing=$(gsettings get "${SCHEMA}" "${KEY}" 2>/dev/null || echo "@as []")
existing_clean=$(echo "${existing}" | tr -d "[]' " | tr ',' '\n' | grep -v '^$' || true)

SLOT=""
for slot in ${existing_clean}; do
    slot_name=$(gsettings get "${SCHEMA}.custom-keybinding:${slot}" name 2>/dev/null | tr -d "'" || true)
    if [[ "${slot_name}" == "${NAME}" ]]; then
        info "Found existing slot: ${slot} — updating."
        SLOT="${slot}"
        break
    fi
done

if [[ -z "${SLOT}" ]]; then
    max_idx=-1
    for slot in ${existing_clean}; do
        idx=$(echo "${slot}" | grep -oP '\d+$' || echo "-1")
        (( idx > max_idx )) && max_idx=${idx}
    done
    NEW_IDX=$(( max_idx + 1 ))
    SLOT="${SLOT_BASE}/purposeos${NEW_IDX}/"
    info "Allocating new slot: ${SLOT}"
    if [[ "${existing}" == "@as []" ]] || [[ "${existing}" == "[]" ]]; then
        new_list="['${SLOT}']"
    else
        new_list=$(echo "${existing}" | sed "s|]$|, '${SLOT}']|")
    fi
    gsettings set "${SCHEMA}" "${KEY}" "${new_list}"
fi

FULL_SCHEMA="${SCHEMA}.custom-keybinding:${SLOT}"
gsettings set "${FULL_SCHEMA}" name    "'${NAME}'"
gsettings set "${FULL_SCHEMA}" command "'${COMMAND}'"
gsettings set "${FULL_SCHEMA}" binding "'${BINDING}'"

echo ""
info "Verifying..."
reg_cmd=$(gsettings get "${FULL_SCHEMA}" command | tr -d "'")
reg_key=$(gsettings get "${FULL_SCHEMA}" binding | tr -d "'")
ok "Command: ${reg_cmd}"
ok "Binding: ${reg_key}"

# Import PATH into systemd user env so subprocesses launched from GNOME can find things
systemctl --user import-environment PATH DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS 2>/dev/null || true

echo ""
echo -e "${GREEN}✓ Ctrl+Shift+O registered.${RESET}"
echo "  Press it from anywhere to open the PurposeOS GUI."
echo ""
echo "  If it still doesn't work after pressing the keys:"
echo "  → Log out and back in once (GNOME reloads keybindings on login)"
echo "  → Or use a different key: ./set_gui_shortcut.sh '<Super>F2'"
echo ""
echo "  To verify in GNOME Settings:"
echo "  Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts"
echo "  You should see 'PurposeOS GUI' listed there."
