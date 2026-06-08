#!/usr/bin/env python3
"""
AuraFrame WiFi Provisioning Portal
Manages hotspot mode and serves a captive portal webpage for WiFi configuration.
Works on both Raspberry Pi 3B+ and Raspberry Pi 5 using NetworkManager.
"""

import os
import sys
import json
import time
import subprocess
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Get unique hotspot SSID from MAC address ─────────────────────────────────
def get_hotspot_ssid():
    try:
        with open("/sys/class/net/wlan0/address", "r") as f:
            mac = f.read().strip().replace(":", "")
            suffix = mac[-4:].upper()
            return f"AuraFrame-{suffix}"
    except Exception:
        return "AuraFrame-Setup"

HOTSPOT_SSID = get_hotspot_ssid()
HOTSPOT_IP = "192.168.4.1"
PORTAL_PORT = 80

# ── Scan nearby WiFi networks ────────────────────────────────────────────────
def scan_wifi_networks():
    """Uses nmcli to scan and list available WiFi networks."""
    networks = []
    try:
        # Trigger a fresh scan
        subprocess.run(["nmcli", "device", "wifi", "rescan"], capture_output=True, timeout=10)
        time.sleep(3)
        # List results
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
            capture_output=True, text=True, timeout=10
        )
        seen = set()
        for line in result.stdout.strip().split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] and parts[0] not in seen:
                ssid = parts[0].strip()
                signal = parts[1].strip() if len(parts) > 1 else "?"
                security = parts[2].strip() if len(parts) > 2 else ""
                if ssid and ssid != HOTSPOT_SSID and ssid != "--":
                    networks.append({"ssid": ssid, "signal": signal, "security": security})
                    seen.add(ssid)
        # Sort by signal strength (highest first)
        networks.sort(key=lambda n: int(n["signal"]) if n["signal"].isdigit() else 0, reverse=True)
    except Exception as e:
        print(f"WiFi scan error: {e}")
    return networks


# ── Start Hotspot Mode ────────────────────────────────────────────────────────
def start_hotspot():
    """Creates a WiFi hotspot using NetworkManager."""
    print(f"[Hotspot] Starting access point: {HOTSPOT_SSID}")
    try:
        # Remove any existing AuraFrame hotspot connection
        subprocess.run(["nmcli", "connection", "delete", "AuraFrame-Hotspot"],
                       capture_output=True, timeout=10)
    except Exception:
        pass

    try:
        # Create a manual open AP connection
        subprocess.run([
            "nmcli", "connection", "add",
            "type", "wifi",
            "ifname", "wlan0",
            "con-name", "AuraFrame-Hotspot",
            "autoconnect", "no",
            "ssid", HOTSPOT_SSID,
            "mode", "ap"
        ], capture_output=True, timeout=10)

        # Configure as open hotspot with static IP
        subprocess.run([
            "nmcli", "connection", "modify", "AuraFrame-Hotspot",
            "802-11-wireless.band", "bg",
            "802-11-wireless.channel", "7",
            "ipv4.addresses", f"{HOTSPOT_IP}/24",
            "ipv4.method", "shared"
        ], capture_output=True, timeout=10)


        # Start the connection
        result = subprocess.run([
            "nmcli", "connection", "up", "AuraFrame-Hotspot"
        ], capture_output=True, text=True, timeout=15)

        if result.returncode != 0:
            print(f"[Hotspot] nmcli hotspot start failed: {result.stderr}")
            return start_hotspot_hostapd()

        print(f"[Hotspot] Access point active: {HOTSPOT_SSID} @ {HOTSPOT_IP}")
        return True
    except Exception as e:
        print(f"[Hotspot] NetworkManager hotspot error: {e}")
        return start_hotspot_hostapd()


def start_hotspot_hostapd():
    """Fallback: start hotspot using hostapd + dnsmasq directly."""
    print("[Hotspot] Falling back to hostapd/dnsmasq...")
    try:
        # Bring down any existing WiFi connection
        subprocess.run(["nmcli", "device", "disconnect", "wlan0"],
                       capture_output=True, timeout=10)
        # Assign static IP
        subprocess.run(["ip", "addr", "flush", "dev", "wlan0"], capture_output=True, timeout=5)
        subprocess.run(["ip", "addr", "add", f"{HOTSPOT_IP}/24", "dev", "wlan0"],
                       capture_output=True, timeout=5)
        subprocess.run(["ip", "link", "set", "wlan0", "up"], capture_output=True, timeout=5)
        # Start hostapd and dnsmasq
        subprocess.run(["systemctl", "start", "hostapd"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "start", "dnsmasq"], capture_output=True, timeout=10)
        print(f"[Hotspot] hostapd/dnsmasq active: {HOTSPOT_SSID} @ {HOTSPOT_IP}")
        return True
    except Exception as e:
        print(f"[Hotspot] hostapd fallback failed: {e}")
        return False


# ── Stop Hotspot Mode ─────────────────────────────────────────────────────────
def stop_hotspot():
    """Tears down the hotspot."""
    print("[Hotspot] Stopping access point...")
    try:
        subprocess.run(["nmcli", "connection", "delete", "AuraFrame-Hotspot"],
                       capture_output=True, timeout=10)
    except Exception:
        pass
    subprocess.run(["systemctl", "stop", "hostapd"], capture_output=True, timeout=10)
    subprocess.run(["systemctl", "stop", "dnsmasq"], capture_output=True, timeout=10)


# ── Connect to WiFi ──────────────────────────────────────────────────────────
def connect_to_wifi(ssid, password):
    """Connects to a WiFi network using NetworkManager. Returns True on success."""
    print(f"[WiFi] Attempting to connect to: {ssid}")
    stop_hotspot()
    time.sleep(2)

    try:
        # Delete any old connection with the same name
        subprocess.run(["nmcli", "connection", "delete", ssid],
                       capture_output=True, timeout=10)
    except Exception:
        pass

    try:
        if password:
            result = subprocess.run([
                "nmcli", "device", "wifi", "connect", ssid,
                "password", password,
                "ifname", "wlan0"
            ], capture_output=True, text=True, timeout=30)
        else:
            result = subprocess.run([
                "nmcli", "device", "wifi", "connect", ssid,
                "ifname", "wlan0"
            ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print(f"[WiFi] Successfully connected to {ssid}")
            # Verify internet connectivity
            time.sleep(3)
            ping = subprocess.run(
                ["ping", "-c", "2", "-W", "5", "8.8.8.8"],
                capture_output=True, timeout=15
            )
            if ping.returncode == 0:
                print("[WiFi] Internet connectivity verified!")
                return True
            else:
                print("[WiFi] Connected but no internet. Continuing anyway...")
                return True
        else:
            print(f"[WiFi] Connection failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"[WiFi] Connection error: {e}")
        return False


# ── Check current WiFi status ─────────────────────────────────────────────────
def is_wifi_connected():
    """Returns True if wlan0 is connected to a WiFi network (not hotspot)."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "DEVICE,STATE", "device"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("wlan0:connected"):
                # Check it's not our hotspot
                conn_result = subprocess.run(
                    ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
                    capture_output=True, text=True, timeout=10
                )
                if "AuraFrame-Hotspot" not in conn_result.stdout:
                    return True
        return False
    except Exception:
        return False


def get_current_wifi_info():
    """Returns dict with current WiFi connection info."""
    info = {"ssid": "", "ip": "", "signal": ""}
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "GENERAL.CONNECTION,IP4.ADDRESS,WIFI.SIGNAL",
             "device", "show", "wlan0"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            if "GENERAL.CONNECTION:" in line:
                info["ssid"] = line.split(":", 1)[1].strip()
            elif "IP4.ADDRESS" in line:
                info["ip"] = line.split(":", 1)[1].strip().split("/")[0]
            elif "WIFI.SIGNAL" in line:
                info["signal"] = line.split(":", 1)[1].strip()
    except Exception:
        pass
    return info


# ═══════════════════════════════════════════════════════════════════════════════
# Captive Portal Web Server
# ═══════════════════════════════════════════════════════════════════════════════

# Callback set by the service coordinator to notify when WiFi is configured
_on_wifi_configured = None

def set_wifi_callback(callback):
    global _on_wifi_configured
    _on_wifi_configured = callback


def _build_network_options_html(networks):
    """Build <option> tags for the network dropdown."""
    if not networks:
        return '<option value="">No networks found — type manually below</option>'
    opts = '<option value="" disabled selected>Select your WiFi network</option>'
    for net in networks:
        lock = "🔒 " if net["security"] else "🔓 "
        bars = int(net["signal"]) if net["signal"].isdigit() else 0
        strength = "████" if bars > 75 else "███░" if bars > 50 else "██░░" if bars > 25 else "█░░░"
        opts += f'<option value="{net["ssid"]}">{lock}{net["ssid"]}  ({strength} {net["signal"]}%)</option>'
    return opts


PORTAL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraFrame — WiFi Setup</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0F0E0C; color: #F5F2EE;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; padding: 20px;
        }
        .container {
            width: 100%%; max-width: 420px;
            background-color: #1A1917; border: 1px solid #2A2927;
            border-radius: 20px; padding: 36px;
            box-shadow: 0 16px 48px rgba(0,0,0,0.6);
        }
        .logo { text-align: center; margin-bottom: 28px; }
        .logo-icon {
            width: 56px; height: 56px; background: linear-gradient(135deg, #C8A97E, #A08050);
            border-radius: 14px; display: inline-flex; justify-content: center; align-items: center;
            color: #0F0E0C; font-weight: bold; font-size: 28px; margin-bottom: 16px;
            box-shadow: 0 4px 12px rgba(200, 169, 126, 0.3);
        }
        h2 { font-size: 22px; font-weight: 500; color: #F5F2EE; }
        p.sub { font-size: 13px; color: #666660; margin-top: 6px; }
        .form-group { margin-bottom: 22px; }
        label {
            display: block; font-size: 11px; color: #888880;
            text-transform: uppercase; letter-spacing: 0.8px;
            margin-bottom: 8px; font-weight: 600;
        }
        select, input[type="text"], input[type="password"] {
            width: 100%%; padding: 13px 16px;
            background-color: #0F0E0C; border: 1px solid #2A2927;
            border-radius: 10px; color: #F5F2EE; font-size: 14px;
            outline: none; transition: border-color 0.2s;
            -webkit-appearance: none; appearance: none;
        }
        select { cursor: pointer; padding-right: 36px;
            background-image: url("data:image/svg+xml,%%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%%23888880'%%3E%%3Cpath d='M6 9L1 4h10z'/%3E%%3C/svg%%3E");
            background-repeat: no-repeat; background-position: right 14px center;
        }
        select:focus, input:focus { border-color: #C8A97E; }
        .manual-toggle {
            font-size: 12px; color: #C8A97E; cursor: pointer;
            text-decoration: underline; margin-top: 8px; display: inline-block;
        }
        .manual-input { display: none; margin-top: 10px; }
        .manual-input.show { display: block; }
        button {
            width: 100%%; padding: 15px; background: linear-gradient(135deg, #C8A97E, #A08050);
            color: #0F0E0C; border: none; border-radius: 12px;
            font-size: 15px; font-weight: 600; cursor: pointer;
            transition: opacity 0.2s, transform 0.1s; margin-top: 8px;
            box-shadow: 0 4px 12px rgba(200, 169, 126, 0.25);
        }
        button:hover { opacity: 0.92; }
        button:active { transform: scale(0.98); }
        .divider { height: 1px; background: #2A2927; margin: 24px 0; }
        .frame-info { text-align: center; }
        .frame-info span { font-size: 11px; color: #555550; }
        .frame-info strong { color: #C8A97E; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <div class="logo-icon">A</div>
            <h2>Welcome to AuraFrame</h2>
            <p class="sub">Connect your frame to your home WiFi network</p>
        </div>

        <form method="POST" action="/connect">
            <div class="form-group">
                <label>WiFi Network</label>
                <select name="ssid" id="ssid-select" onchange="document.getElementById('manual-ssid').value=this.value">
                    {NETWORK_OPTIONS}
                </select>
                <span class="manual-toggle" onclick="document.getElementById('manual-box').classList.toggle('show')">
                    Type network name manually
                </span>
                <div id="manual-box" class="manual-input">
                    <input type="text" id="manual-ssid" name="manual_ssid" placeholder="Enter WiFi name (SSID)">
                </div>
            </div>

            <div class="form-group">
                <label>WiFi Password</label>
                <input type="password" name="password" placeholder="Enter WiFi password">
            </div>

            <div class="form-group">
                <label>Frame Name (optional)</label>
                <input type="text" name="frame_name" placeholder="e.g. Living Room" value="My AuraFrame" maxlength="30">
            </div>

            <button type="submit">Connect Frame</button>
        </form>

        <div class="divider"></div>
        <div class="frame-info">
            <span>Frame ID</span><br>
            <strong>{FRAME_SSID}</strong>
        </div>
    </div>
</body>
</html>"""


SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraFrame — Connected!</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, sans-serif;
            background-color: #0F0E0C; color: #F5F2EE;
            display: flex; justify-content: center; align-items: center;
            height: 100vh;
        }
        .container {
            text-align: center; max-width: 400px; padding: 40px;
            background-color: #1A1917; border: 1px solid #2A2927;
            border-radius: 20px; box-shadow: 0 16px 48px rgba(0,0,0,0.6);
        }
        .check { font-size: 56px; margin-bottom: 20px; }
        h2 { font-size: 22px; font-weight: 500; margin-bottom: 12px; color: #39C78F; }
        p { font-size: 14px; color: #888880; line-height: 1.7; }
        .steps { margin-top: 24px; text-align: left; padding: 16px 20px;
            background: #0F0E0C; border-radius: 12px; border: 1px solid #2A2927; }
        .steps li { margin-bottom: 8px; font-size: 13px; color: #AAA8A0; }
        .steps li strong { color: #C8A97E; }
    </style>
</head>
<body>
    <div class="container">
        <div class="check">✓</div>
        <h2>WiFi Connected!</h2>
        <p>Your AuraFrame is now connecting to <strong>{SSID}</strong>.</p>
        <div class="steps">
            <ol>
                <li>This hotspot will disappear in a few seconds</li>
                <li>Reconnect your phone to <strong>{SSID}</strong></li>
                <li>Open the <strong>AuraFrame app</strong> to pair and send photos</li>
            </ol>
        </div>
    </div>
</body>
</html>"""


FAIL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraFrame — Connection Failed</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, sans-serif;
            background-color: #0F0E0C; color: #F5F2EE;
            display: flex; justify-content: center; align-items: center;
            height: 100vh; margin: 0;
        }
        .container {
            text-align: center; max-width: 400px; padding: 40px;
            background-color: #1A1917; border: 1px solid #2A2927;
            border-radius: 20px; box-shadow: 0 16px 48px rgba(0,0,0,0.6);
        }
        .icon { font-size: 48px; margin-bottom: 20px; }
        h2 { font-size: 20px; color: #FF7070; margin-bottom: 12px; }
        p { font-size: 13px; color: #888880; line-height: 1.6; margin-bottom: 20px; }
        a { color: #C8A97E; text-decoration: none; font-weight: 600;
            padding: 12px 24px; border: 1px solid #C8A97E; border-radius: 10px;
            display: inline-block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">✗</div>
        <h2>Connection Failed</h2>
        <p>Could not connect to "<strong>{SSID}</strong>".<br>Please check your password and try again.</p>
        <a href="/">Try Again</a>
    </div>
</body>
</html>"""


class PortalHandler(BaseHTTPRequestHandler):
    """HTTP handler for the captive portal."""

    def log_message(self, format, *args):
        print(f"[Portal] {args[0]}")

    def do_GET(self):
        # All GET requests serve the setup form (captive portal redirect)
        networks = scan_wifi_networks()
        options_html = _build_network_options_html(networks)
        page = PORTAL_HTML_TEMPLATE.replace("{NETWORK_OPTIONS}", options_html)
        page = page.replace("{FRAME_SSID}", HOTSPOT_SSID)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))

    def do_POST(self):
        if self.path == "/connect":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            params = urllib.parse.parse_qs(post_data)

            # Prefer manual SSID if provided, else use dropdown
            ssid = params.get("manual_ssid", [""])[0].strip()
            if not ssid:
                ssid = params.get("ssid", [""])[0].strip()
            password = params.get("password", [""])[0]
            frame_name = params.get("frame_name", ["My AuraFrame"])[0].strip()

            if not ssid:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return

            print(f"[Portal] WiFi credentials received: SSID='{ssid}', Frame='{frame_name}'")

            # Save frame name to .env
            _update_env("FRAME_NAME", frame_name)

            # Attempt connection in a thread so we can serve the response first
            def do_connect():
                time.sleep(2)  # Let the response page render
                success = connect_to_wifi(ssid, password)
                if success and _on_wifi_configured:
                    _on_wifi_configured(ssid, frame_name)
                elif not success:
                    # Connection failed — restart hotspot
                    print("[Portal] Connection failed. Restarting hotspot...")
                    time.sleep(3)
                    start_hotspot()

            # Serve success page immediately (optimistic)
            success_page = SUCCESS_HTML.replace("{SSID}", ssid)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(success_page.encode("utf-8"))

            threading.Thread(target=do_connect, daemon=True).start()


def _update_env(key, value):
    """Update a key in the .env file."""
    env_path = os.path.join(BASE_DIR, ".env")
    # If /opt/auraframe/.env exists, use it
    opt_path = "/opt/auraframe/.env"
    if os.path.exists(opt_path):
        env_path = opt_path

    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()

    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")

    # Ensure parent directory exists (especially for /opt/auraframe)
    try:
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        with open(env_path, "w") as f:
            f.writelines(lines)
        print(f"[Config] Updated {key} in .env ({env_path})")
    except Exception as e:
        print(f"[Config] Error writing .env at {env_path}: {e}")


# ── Portal Server ─────────────────────────────────────────────────────────────
_server = None

def start_portal():
    """Start the captive portal web server (blocking)."""
    global _server
    print(f"[Portal] Starting captive portal on {HOTSPOT_IP}:{PORTAL_PORT}")
    _server = HTTPServer(("0.0.0.0", PORTAL_PORT), PortalHandler)
    try:
        _server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _server.server_close()
        print("[Portal] Server stopped.")


def stop_portal():
    """Stop the captive portal web server."""
    global _server
    if _server:
        print("[Portal] Shutting down portal server...")
        _server.shutdown()
        _server = None


# ── Convenience: run portal in background thread ─────────────────────────────
def start_portal_thread():
    """Start portal server in a background thread. Returns the thread."""
    t = threading.Thread(target=start_portal, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    # Standalone test: start hotspot + portal
    start_hotspot()
    start_portal()
