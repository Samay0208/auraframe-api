#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# AuraFrame — One-Command Raspberry Pi Installer
# Supports: Raspberry Pi 3B+ and Raspberry Pi 5
# OS: Raspberry Pi OS Lite (Bookworm 64-bit recommended)
# Usage: sudo bash setup.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/auraframe"
SERVICE_USER="${SUDO_USER:-pi}"


# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
GOLD='\033[0;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[AuraFrame]${NC} $1"; }
warn() { echo -e "${GOLD}[Warning]${NC} $1"; }
err()  { echo -e "${RED}[Error]${NC} $1"; exit 1; }

# ── Root Check ────────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    err "Please run as root: sudo bash setup.sh"
fi

# ── Detect Pi Model ──────────────────────────────────────────────────────────
PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
log "Detected board: ${PI_MODEL}"

if echo "$PI_MODEL" | grep -qi "Pi 5"; then
    PI_TYPE="rpi5"
    log "Configuration: Raspberry Pi 5 mode"
elif echo "$PI_MODEL" | grep -qi "Pi 3"; then
    PI_TYPE="rpi3"
    log "Configuration: Raspberry Pi 3B+ mode"
else
    PI_TYPE="generic"
    warn "Unrecognized Pi model. Using generic configuration."
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Install System Dependencies
# ══════════════════════════════════════════════════════════════════════════════
log "Updating package lists..."
apt-get update -qq

log "Installing system dependencies..."
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-pygame python3-pil python3-requests \
    network-manager hostapd dnsmasq \
    fbi plymouth plymouth-themes \
    git curl wget unzip \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    fonts-dejavu-core \
    2>/dev/null

# Ensure NetworkManager is managing WiFi (not wpa_supplicant)
log "Configuring NetworkManager as primary network manager..."
systemctl disable --now wpa_supplicant 2>/dev/null || true
systemctl enable --now NetworkManager 2>/dev/null || true

# Tell NetworkManager to manage wlan0
cat > /etc/NetworkManager/conf.d/10-auraframe.conf << 'NMCONF'
[device]
wifi.scan-rand-mac-address=no

[ifupdown]
managed=true
NMCONF

# Disable hostapd and dnsmasq by default (only activated during setup mode)
systemctl disable hostapd 2>/dev/null || true
systemctl disable dnsmasq 2>/dev/null || true
systemctl stop hostapd 2>/dev/null || true
systemctl stop dnsmasq 2>/dev/null || true

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Install AuraFrame Application Files
# ══════════════════════════════════════════════════════════════════════════════
log "Installing AuraFrame to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/cache"
mkdir -p "${INSTALL_DIR}/boot"

# Copy all Python files
cp "${SCRIPT_DIR}/auraframe_service.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/frame_display.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/wifi_portal.py" "${INSTALL_DIR}/"

# Copy boot assets
if [ -f "${SCRIPT_DIR}/boot/splash.png" ]; then
    cp "${SCRIPT_DIR}/boot/splash.png" "${INSTALL_DIR}/boot/"
fi

# Set ownership
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Configure hostapd (Access Point for WiFi Setup)
# ══════════════════════════════════════════════════════════════════════════════
log "Configuring hostapd for setup access point..."

# Generate unique SSID from MAC address
WLAN_MAC=$(cat /sys/class/net/wlan0/address 2>/dev/null | sed 's/://g' | tail -c 5 | tr '[:lower:]' '[:upper:]')
AP_SSID="AuraFrame-${WLAN_MAC}"

cat > /etc/hostapd/hostapd.conf << HOSTAPD
interface=wlan0
driver=nl80211
ssid=${AP_SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
# Open network (no password for setup portal)
HOSTAPD

# Point hostapd to its config
sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd 2>/dev/null || true

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Configure dnsmasq (DHCP for Setup Mode)
# ══════════════════════════════════════════════════════════════════════════════
log "Configuring dnsmasq for captive portal..."

# Backup original config
[ -f /etc/dnsmasq.conf ] && cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup

cat > /etc/dnsmasq.d/auraframe.conf << 'DNSMASQ'
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/192.168.4.1
DNSMASQ

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Custom Boot Splash (Remove All Pi Branding)
# ══════════════════════════════════════════════════════════════════════════════
log "Configuring clean branded boot sequence..."

# Suppress all boot text, rainbow, Pi logos
CMDLINE="/boot/firmware/cmdline.txt"
[ ! -f "$CMDLINE" ] && CMDLINE="/boot/cmdline.txt"

if [ -f "$CMDLINE" ]; then
    # Remove any existing splash/quiet/logo params to avoid duplicates
    sed -i 's/ quiet//g; s/ splash//g; s/ logo.nologo//g; s/ vt.global_cursor_default=0//g; s/ loglevel=[0-9]//g; s/ console=tty3//g' "$CMDLINE"
    # Append our clean boot params
    sed -i 's/$/ quiet splash logo.nologo vt.global_cursor_default=0 loglevel=0 console=tty3/' "$CMDLINE"
    log "Boot command line updated: ${CMDLINE}"
fi

# Disable rainbow splash
CONFIG="/boot/firmware/config.txt"
[ ! -f "$CONFIG" ] && CONFIG="/boot/config.txt"

if [ -f "$CONFIG" ]; then
    grep -q "disable_splash" "$CONFIG" || echo "disable_splash=1" >> "$CONFIG"
    # Force HDMI output for the 5-inch display
    grep -q "hdmi_force_hotplug" "$CONFIG" || echo "hdmi_force_hotplug=1" >> "$CONFIG"
    grep -q "hdmi_group" "$CONFIG" || echo "hdmi_group=2" >> "$CONFIG"
    grep -q "hdmi_mode" "$CONFIG" || echo "hdmi_mode=87" >> "$CONFIG"
    grep -q "hdmi_cvt" "$CONFIG" || echo "hdmi_cvt=800 480 60 6 0 0 0" >> "$CONFIG"
    # Disable screen blanking
    grep -q "consoleblank=0" "$CONFIG" || echo "consoleblank=0" >> "$CONFIG"
    log "Boot config updated: ${CONFIG}"
fi

# Install custom Plymouth splash theme
PLYMOUTH_DIR="/usr/share/plymouth/themes/auraframe"
mkdir -p "${PLYMOUTH_DIR}"

if [ -f "${INSTALL_DIR}/boot/splash.png" ]; then
    cp "${INSTALL_DIR}/boot/splash.png" "${PLYMOUTH_DIR}/splash.png"
fi

cat > "${PLYMOUTH_DIR}/auraframe.plymouth" << 'PLYMOUTH'
[Plymouth Theme]
Name=AuraFrame
Description=AuraFrame Digital Photo Frame Boot Splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/auraframe
ScriptFile=/usr/share/plymouth/themes/auraframe/auraframe.script
PLYMOUTH

cat > "${PLYMOUTH_DIR}/auraframe.script" << 'PLYSCRIPT'
wallpaper = Image("splash.png");
screen_width = Window.GetWidth();
screen_height = Window.GetHeight();
resized = wallpaper.Scale(screen_width, screen_height);
sprite = Sprite(resized);
sprite.SetX(0);
sprite.SetY(0);
sprite.SetZ(-100);
PLYSCRIPT

# Set AuraFrame as the default Plymouth theme
plymouth-set-default-theme auraframe 2>/dev/null || true
update-initramfs -u 2>/dev/null || true

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Disable Login Prompt & Desktop Environment
# ══════════════════════════════════════════════════════════════════════════════
log "Disabling login prompt and desktop..."

# Disable getty on tty1 (no login prompt on screen)
systemctl disable getty@tty1 2>/dev/null || true

# Disable any desktop manager
systemctl disable lightdm 2>/dev/null || true
systemctl disable gdm3 2>/dev/null || true

# Hide cursor globally
mkdir -p /etc/X11/xinit
grep -q "xdotool" /etc/rc.local 2>/dev/null || true

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: Create systemd Service (Auto-start on Boot)
# ══════════════════════════════════════════════════════════════════════════════
log "Creating AuraFrame systemd service..."

cat > /etc/systemd/system/auraframe.service << SERVICE
[Unit]
Description=AuraFrame Digital Photo Frame Service
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=simple
User=root
Environment="DISPLAY=:0"
Environment="SDL_FBDEV=/dev/fb0"
Environment="SDL_VIDEODRIVER=fbcon"
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/auraframe_service.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable auraframe.service

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: Disable Screen Blanking & Power Management
# ══════════════════════════════════════════════════════════════════════════════
log "Disabling screen blanking and power management..."

# Prevent screen from blanking
cat > /etc/profile.d/auraframe-display.sh << 'DISPLAYCONF'
export TERM=linux
setterm -blank 0 -powerdown 0 -powersave off 2>/dev/null || true
DISPLAYCONF

# DPMS off
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/10-blanking.conf << 'XORGCONF'
Section "ServerFlags"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection
XORGCONF

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: Write Environment Config Template
# ══════════════════════════════════════════════════════════════════════════════
log "Writing environment configuration..."

if [ ! -f "${INSTALL_DIR}/.env" ]; then
    cat > "${INSTALL_DIR}/.env" << ENVFILE
# AuraFrame Configuration
# These values are set automatically during pairing
API_BASE=https://auraframe-api.vercel.app
FRAME_ID=
API_KEY=
FRAME_NAME=My AuraFrame
SLIDE_DURATION=15
POLL_INTERVAL=30
DISPLAY_WIDTH=800
DISPLAY_HEIGHT=480
ENVFILE
    chown "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/.env"
fi

# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════
log "════════════════════════════════════════════════════════════"
log "  AuraFrame installation complete!"
log "  Board: ${PI_MODEL}"
log "  Hotspot SSID: ${AP_SSID}"
log "  Install dir: ${INSTALL_DIR}"
log ""
log "  Reboot now:  sudo reboot"
log "  After reboot, the frame will enter WiFi setup mode."
log "  Connect your phone to '${AP_SSID}' to configure."
log "════════════════════════════════════════════════════════════"
