#!/usr/bin/env bash
# install.sh — PurposeOS v2 Installer
#
# Supports: Fedora/RHEL, Ubuntu/Debian, Arch/Manjaro, openSUSE
# Run as your normal user (NOT root). sudo is used only for system packages.

set -euo pipefail

CYAN='\033[36m'; GREEN='\033[32m'; YELLOW='\033[33m'
RED='\033[31m'; RESET='\033[0m'; BOLD='\033[1m'
info() { echo -e "${CYAN}→${RESET}  $*"; }
ok()   { echo -e "${GREEN}✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }
die()  { echo -e "${RED}✗${RESET}  $*" >&2; exit 1; }

# SCRIPT_DIR = scripts/  PROJECT_ROOT = the repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║   PurposeOS v2 — Installer           ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════╝${RESET}"
echo ""

# ── 1. Verify source layout ────────────────────────────────────────────────────
info "Verifying source layout..."
PKG_SRC="${PROJECT_ROOT}/purposeos"
[[ -d "${PKG_SRC}" ]]                  || die "purposeos/ not found. Run from the project root."
[[ -f "${PKG_SRC}/main.py" ]]          || die "purposeos/main.py not found."
[[ -f "${PKG_SRC}/adctl.py" ]]         || die "purposeos/adctl.py not found."
[[ -f "${PKG_SRC}/cli/parser.py" ]]    || die "purposeos/cli/parser.py not found."
[[ -f "${PKG_SRC}/core/config.py" ]]   || die "purposeos/core/config.py not found."
[[ -f "${PKG_SRC}/i18n/__init__.py" ]] || die "purposeos/i18n/__init__.py not found."
[[ -f "${PKG_SRC}/gui/main.py" ]]      || die "purposeos/gui/main.py not found."
[[ -f "${PROJECT_ROOT}/pyproject.toml" ]] || die "pyproject.toml not found."
[[ -f "${SCRIPT_DIR}/uninstall.sh" ]]  || die "scripts/uninstall.sh not found."
ok "Source layout verified."

# ── 2. System packages ─────────────────────────────────────────────────────────
detect_distro() {
    if   command -v dnf    &>/dev/null; then echo "dnf"
    elif command -v apt    &>/dev/null; then echo "apt"
    elif command -v pacman &>/dev/null; then echo "pacman"
    elif command -v zypper &>/dev/null; then echo "zypper"
    else echo "unknown"; fi
}
PKG_MGR="$(detect_distro)"
info "Package manager: ${PKG_MGR}"

case "${PKG_MGR}" in
    dnf)
        info "Installing system packages via dnf..."
        sudo dnf install -y --skip-unavailable \
            python3 python3-pip python3-gobject \
            gtk4 libnotify xdotool xprop \
            python3-wnck libcanberra-gtk3 pipewire-utils \
            || die "dnf install failed."
        ;;
    apt)
        info "Installing system packages via apt..."
        sudo apt-get update -qq
        sudo apt-get install -y \
            python3 python3-pip python3-gi \
            gir1.2-gtk-4.0 libnotify-bin xdotool \
            x11-utils libcanberra-gtk3-module \
            || die "apt install failed."
        ;;
    pacman)
        info "Installing system packages via pacman..."
        sudo pacman -Sy --noconfirm --needed \
            python python-pip python-gobject \
            gtk4 libnotify xdotool xorg-xprop libcanberra \
            || die "pacman install failed."
        ;;
    zypper)
        info "Installing system packages via zypper..."
        sudo zypper install -y --no-recommends \
            python3 python3-pip python3-gobject \
            gtk4-tools libnotify-tools xdotool xprop libcanberra-gtk3 \
            || die "zypper install failed."
        ;;
    *)
        warn "Unknown distro — skipping system packages."
        warn "Install manually: python3 python3-pip python3-gobject gtk4 libnotify xdotool"
        ;;
esac
ok "System packages done."

# ── 3. Python packages ─────────────────────────────────────────────────────────
info "Installing Python packages..."
pip install --user --upgrade pip --quiet
if [[ -f "${PROJECT_ROOT}/requirements.txt" ]]; then
    pip install --user -r "${PROJECT_ROOT}/requirements.txt" || die "pip install failed."
fi
ok "Python packages installed."

# ── 4. Install the purposeos package ──────────────────────────────────────────
info "Installing PurposeOS package..."
pip install --user "${PROJECT_ROOT}" || die "Package install failed."
ok "PurposeOS package installed."

# ── 5. Entry-point wrapper scripts ────────────────────────────────────────────
LOCAL_BIN="${HOME}/.local/bin"
mkdir -p "${LOCAL_BIN}"
info "Writing entry-point scripts..."

if [[ ! -f "${LOCAL_BIN}/purposeos-daemon" ]]; then
    printf '#!/usr/bin/env python3\nfrom purposeos.main import main\nmain()\n' \
        > "${LOCAL_BIN}/purposeos-daemon"
    chmod +x "${LOCAL_BIN}/purposeos-daemon"
    ok "Created purposeos-daemon"
else
    ok "purposeos-daemon already exists"
fi

if [[ ! -f "${LOCAL_BIN}/adctl" ]]; then
    printf '#!/usr/bin/env python3\nfrom purposeos.cli.parser import main\nif __name__ == "__main__":\n    main()\n' \
        > "${LOCAL_BIN}/adctl"
    chmod +x "${LOCAL_BIN}/adctl"
    ok "Created adctl"
else
    ok "adctl already exists"
fi

[[ ":${PATH}:" != *":${LOCAL_BIN}:"* ]] && \
    warn "${LOCAL_BIN} not in PATH. Add to your shell profile:" && \
    warn "  export PATH=\"\${HOME}/.local/bin:\${PATH}\"" || true

# ── 6. Install manifest ────────────────────────────────────────────────────────
MANIFEST_DIR="${HOME}/.local/share/purposeos"
mkdir -p "${MANIFEST_DIR}"

cp "${SCRIPT_DIR}/uninstall.sh" "${MANIFEST_DIR}/uninstall.sh"
chmod +x "${MANIFEST_DIR}/uninstall.sh"
echo "${PROJECT_ROOT}" > "${MANIFEST_DIR}/source_path"
ok "Manifest written to ${MANIFEST_DIR}"

# ── 7. Runtime directories ─────────────────────────────────────────────────────
info "Creating runtime directories..."
mkdir -p \
    "${HOME}/.local/share/automation-daemon/logs" \
    "${HOME}/.config/automation-daemon/notes"
ok "Runtime directories ready."

# ── 8. systemd user service ────────────────────────────────────────────────────
SYSTEMD_DIR="${HOME}/.config/systemd/user"
mkdir -p "${SYSTEMD_DIR}"

SERVICE_SRC=""
for candidate in \
    "${SCRIPT_DIR}/purposeos.service" \
    "${PROJECT_ROOT}/purposeos.service"; do
    [[ -f "${candidate}" ]] && { SERVICE_SRC="${candidate}"; break; }
done

if [[ -n "${SERVICE_SRC}" ]]; then
    info "Installing systemd service..."
    cp "${SERVICE_SRC}" "${SYSTEMD_DIR}/purposeos.service"
else
    warn "purposeos.service not found — writing default..."
    cat > "${SYSTEMD_DIR}/purposeos.service" << 'SVCEOF'
[Unit]
Description=PurposeOS Desktop Automation Daemon
After=graphical-session.target dbus.service
Wants=graphical-session.target

[Service]
Type=simple
ExecStartPre=/bin/bash -c 'systemctl --user import-environment DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR XAUTHORITY 2>/dev/null; true'
ExecStart=%h/.local/bin/purposeos-daemon
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
PassEnvironment=DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR XAUTHORITY HOME USER

[Install]
WantedBy=default.target
SVCEOF
fi

systemctl --user daemon-reload
systemctl --user enable purposeos.service
ok "purposeos.service installed and enabled."

info "Starting daemon..."
systemctl --user start purposeos.service || true
sleep 2
systemctl --user is-active --quiet purposeos.service \
    && ok "Daemon is running." \
    || warn "Daemon not confirmed active. Run: adctl start"

# ── 9. Desktop entries ─────────────────────────────────────────────────────────
APPS_DIR="${HOME}/.local/share/applications"
mkdir -p "${APPS_DIR}"
info "Installing .desktop entries..."

cat > "${APPS_DIR}/purposeos-quicknote.desktop" << DESKEOF
[Desktop Entry]
Name=PurposeOS Quick Note
Comment=Open PurposeOS floating note window
Exec=${LOCAL_BIN}/adctl quicknote
Icon=accessories-text-editor
Terminal=false
Type=Application
Categories=Utility;TextEditor;
StartupNotify=false
DESKEOF

cat > "${APPS_DIR}/purposeos-gui.desktop" << DESKEOF
[Desktop Entry]
Name=PurposeOS
Comment=Open PurposeOS dashboard
Exec=${LOCAL_BIN}/adctl gui
Icon=preferences-system
Terminal=false
Type=Application
Categories=Utility;Settings;
StartupNotify=false
DESKEOF

update-desktop-database "${APPS_DIR}" 2>/dev/null || true
ok ".desktop entries installed."

# ── 10. Keyboard shortcuts (GNOME) ────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Optional: GNOME keyboard shortcuts ──────────────────────────${RESET}"

chmod +x "${SCRIPT_DIR}/set_notes_shortcut.sh" "${SCRIPT_DIR}/set_gui_shortcut.sh" 2>/dev/null || true

if command -v gsettings &>/dev/null; then
    echo ""
    echo -e "  ${BOLD}Ctrl+Shift+P${RESET} → Quick Note"
    printf "  Register now? [y/N]: "
    read -r ans_notes
    if [[ "${ans_notes,,}" == "y" ]]; then
        if [[ -f "${SCRIPT_DIR}/set_notes_shortcut.sh" ]]; then
            bash "${SCRIPT_DIR}/set_notes_shortcut.sh" && ok "Quick Note shortcut registered."
        else
            warn "set_notes_shortcut.sh not found — run manually later."
        fi
    fi

    echo ""
    echo -e "  ${BOLD}Ctrl+Shift+O${RESET} → GUI dashboard"
    printf "  Register now? [y/N]: "
    read -r ans_gui
    if [[ "${ans_gui,,}" == "y" ]]; then
        if [[ -f "${SCRIPT_DIR}/set_gui_shortcut.sh" ]]; then
            bash "${SCRIPT_DIR}/set_gui_shortcut.sh" && ok "GUI shortcut registered."
        else
            warn "set_gui_shortcut.sh not found — run manually later."
        fi
    fi
else
    warn "gsettings not available. Register shortcuts manually:"
    warn "  ./scripts/set_notes_shortcut.sh   (Ctrl+Shift+P)"
    warn "  ./scripts/set_gui_shortcut.sh     (Ctrl+Shift+O)"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║   PurposeOS v2 installed!            ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════╝${RESET}"
echo ""