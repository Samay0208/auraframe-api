#!/usr/bin/env python3
"""
AuraFrame Master Service Coordinator
Single entry point that orchestrates WiFi provisioning, display, and slideshow.

Boot Flow:
  Power On → Splash → Check WiFi → [No]  → Hotspot + Portal + Setup Screen
                                   [Yes] → Slideshow + Cloud Sync

Runtime:
  - Monitors WiFi connectivity (auto-recover if drops)
  - Listens for reset commands (GPIO button / cloud API / auto)
  - Handles graceful shutdown

Works on both Raspberry Pi 3B+ and Raspberry Pi 5.
"""

import os
import sys
import time
import signal
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from frame_display import FrameDisplay, PhotoSync, load_config, run_slideshow
from wifi_portal import (
    start_hotspot, stop_hotspot, start_portal_thread, stop_portal,
    is_wifi_connected, get_hotspot_ssid, set_wifi_callback,
    HOTSPOT_SSID
)

# ── Configuration ─────────────────────────────────────────────────────────────
BUTTON_PIN = 21
HOLD_THRESHOLD = 5.0  # seconds to hold button for reset
WIFI_CHECK_INTERVAL = 60  # seconds between WiFi checks
WIFI_RETRY_DELAY = 10  # seconds before retrying WiFi setup

# ── Global State ──────────────────────────────────────────────────────────────
display = FrameDisplay()
sync = PhotoSync()
_wifi_configured_event = threading.Event()
_wifi_ssid = ""
_reset_requested = threading.Event()


def on_wifi_configured(ssid, frame_name):
    """Callback from wifi_portal when WiFi credentials are submitted."""
    global _wifi_ssid
    _wifi_ssid = ssid
    print(f"[Service] WiFi configured: {ssid}, Frame: {frame_name}")
    _wifi_configured_event.set()


# Register callback
set_wifi_callback(on_wifi_configured)


# ══════════════════════════════════════════════════════════════════════════════
# GPIO Button Monitor (optional — works only on real Pi hardware)
# ══════════════════════════════════════════════════════════════════════════════

def start_button_monitor():
    """Monitor GPIO button for factory reset. Runs in background thread."""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        print(f"[Button] GPIO monitoring active on Pin {BUTTON_PIN}")
    except (ImportError, RuntimeError) as e:
        print(f"[Button] GPIO not available ({e}). Physical button disabled.")
        return

    def monitor():
        press_start = None
        try:
            while True:
                pressed = not GPIO.input(BUTTON_PIN)
                if pressed:
                    if press_start is None:
                        press_start = time.time()
                        print("[Button] Press detected...")
                    elif time.time() - press_start >= HOLD_THRESHOLD:
                        print("[Button] 5-second hold — reset triggered!")
                        _reset_requested.set()
                        press_start = None
                        time.sleep(2)  # Debounce
                else:
                    if press_start is not None:
                        print("[Button] Released early.")
                    press_start = None
                time.sleep(0.1)
        except Exception:
            pass
        finally:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()


# ══════════════════════════════════════════════════════════════════════════════
# WiFi Setup Mode
# ══════════════════════════════════════════════════════════════════════════════

def enter_setup_mode():
    """Enter WiFi provisioning mode: hotspot + portal + setup display."""
    print("[Service] ═══ Entering WiFi Setup Mode ═══")
    _wifi_configured_event.clear()

    # Start hotspot
    hotspot_ssid = get_hotspot_ssid()
    success = start_hotspot()
    if not success:
        print("[Service] Failed to start hotspot!")
        display.show_connecting("Retrying setup...")
        time.sleep(5)
        return False

    # Show setup screen on display
    display.show_setup(hotspot_ssid)

    # Start captive portal web server
    portal_thread = start_portal_thread()

    # Wait for WiFi credentials or reset
    print("[Service] Waiting for WiFi credentials via captive portal...")
    while not _wifi_configured_event.is_set():
        display._pump_events()
        if not display.running:
            stop_portal()
            stop_hotspot()
            return False
        time.sleep(0.5)

    # WiFi credentials received — show connecting screen
    display.show_connecting(_wifi_ssid)
    time.sleep(3)

    # Stop portal
    stop_portal()

    # Check if actually connected
    retries = 5
    for i in range(retries):
        if is_wifi_connected():
            print("[Service] WiFi connection confirmed!")
            display.show_connected(_wifi_ssid)
            time.sleep(4)
            return True
        print(f"[Service] Waiting for WiFi connection... ({i+1}/{retries})")
        time.sleep(3)

    print("[Service] WiFi connection not confirmed after retries.")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Auto Registration and Pairing Check
# ══════════════════════════════════════════════════════════════════════════════

def self_register_frame():
    """Register the frame automatically with the backend if config is empty."""
    import requests
    from wifi_portal import _update_env
    
    # Reload config first
    load_config()
    import frame_display
    
    if frame_display.FRAME_ID and frame_display.API_KEY:
        return True
        
    print("[Service] No FRAME_ID or API_KEY found. Registering automatically...")
    display.show_connecting("Registering frame...")
    
    url = f"{frame_display.API_BASE}/frames/self-register"
    try:
        res = requests.post(url, json={"name": frame_display.FRAME_NAME}, timeout=15)
        if res.status_code == 200:
            data = res.json()
            new_fid = data["frameId"]
            new_akey = data["apiKey"]
            pairing_pin = data["pairingPin"]
            
            print(f"[Service] Registered successfully! ID: {new_fid}, PIN: {pairing_pin}")
            
            # Save to env
            _update_env("FRAME_ID", new_fid)
            _update_env("API_KEY", new_akey)
            _update_env("PAIRING_PIN", pairing_pin)
            
            # Reload config
            load_config()
            return True
        else:
            print(f"[Service] Registration endpoint returned status {res.status_code}")
            display.show_connecting("Registration failed...")
            time.sleep(3)
    except Exception as e:
        print(f"[Service] Registration error: {e}")
        display.show_connecting("Registration error...")
        time.sleep(3)
    return False


def check_pairing_status():
    """Poll API to check if the frame has been paired by an owner."""
    import requests
    # Reload config
    load_config()
    import frame_display
    
    fid = frame_display.FRAME_ID
    akey = frame_display.API_KEY
    abase = frame_display.API_BASE
    
    if not fid or not akey:
        return False, None
        
    url = f"{abase}/frames/{fid}/pairing-status"
    headers = {"Authorization": f"Bearer {akey}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get("paired", False), data.get("pairingPin")
        elif res.status_code in (401, 404):
            print(f"[Service] Credentials invalid ({res.status_code}). Clearing config.")
            from wifi_portal import _update_env
            _update_env("FRAME_ID", "")
            _update_env("API_KEY", "")
            _update_env("PAIRING_PIN", "")
            load_config()
    except Exception as e:
        print(f"[Service] Error checking pairing status: {e}")
    return False, None


# ══════════════════════════════════════════════════════════════════════════════
# Main Service Loop
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point for the AuraFrame service."""
    print("═══════════════════════════════════════════════════════════")
    print("  AuraFrame Digital Photo Frame Service")
    print("  Starting up...")
    print("═══════════════════════════════════════════════════════════")

    # Load configuration
    load_config()

    # Initialize display
    display.init()
    display.show_boot()
    time.sleep(2)

    # Start GPIO button monitor (in background)
    start_button_monitor()

    # ── Main Loop ─────────────────────────────────────────────────────────────
    while display.running:
        # Check if WiFi is connected
        print("[Service] Checking WiFi connectivity...")
        wifi_ok = False

        for attempt in range(3):
            if is_wifi_connected():
                wifi_ok = True
                break
            print(f"[Service] WiFi not connected. Retrying... ({attempt+1}/3)")
            time.sleep(2)

        if not wifi_ok:
            # No WiFi — enter setup mode
            print("[Service] No WiFi connection. Entering setup mode.")
            setup_success = enter_setup_mode()
            if not setup_success:
                if not display.running:
                    break
                # Setup failed — wait and retry
                print(f"[Service] Setup failed. Retrying in {WIFI_RETRY_DELAY}s...")
                time.sleep(WIFI_RETRY_DELAY)
                continue
            # After successful setup, reload config
            load_config()

        # Check self-registration
        import frame_display
        if not frame_display.FRAME_ID or not frame_display.API_KEY:
            if not self_register_frame():
                print("[Service] Self-registration failed. Retrying setup loop...")
                time.sleep(5)
                continue

        # Check pairing status
        paired, pairing_pin = check_pairing_status()
        if not paired:
            print(f"[Service] Frame is not paired yet. Displaying PIN: {pairing_pin}")
            # Try to get pairing pin from env/config if not returned
            if not pairing_pin:
                env_path = os.path.join(BASE_DIR, ".env")
                if not os.path.exists(env_path):
                    env_path = "/opt/auraframe/.env"
                if os.path.exists(env_path):
                    try:
                        with open(env_path, "r") as f:
                            for line in f:
                                if "PAIRING_PIN=" in line:
                                    pairing_pin = line.split("=", 1)[1].strip().strip('"').strip("'")
                    except Exception:
                        pass
            
            if not pairing_pin:
                pairing_pin = "------"
                
            display.show_pairing(pairing_pin)
            
            is_paired = False
            last_poll = 0
            poll_interval = 5
            
            while not is_paired and display.running:
                display._pump_events()
                now = time.time()
                if now - last_poll >= poll_interval:
                    if not is_wifi_connected():
                        print("[Service] WiFi connection lost during pairing status check.")
                        break
                    
                    p_status, _ = check_pairing_status()
                    if p_status:
                        is_paired = True
                        display.show_connected(_wifi_ssid or "WiFi")
                        time.sleep(4)
                    last_poll = now
                time.sleep(0.1)
                
            if not is_paired:
                # Loop back to check WiFi or retry
                continue

        # ── Connected — Run Slideshow ─────────────────────────────────────────
        print("[Service] WiFi connected. Starting slideshow...")
        _reset_requested.clear()

        # Run slideshow in a loop, checking for reset requests
        def check_reset():
            while not _reset_requested.is_set() and display.running:
                time.sleep(0.5)
            if _reset_requested.is_set():
                print("[Service] Reset requested during slideshow!")

        reset_thread = threading.Thread(target=check_reset, daemon=True)
        reset_thread.start()

        result = run_slideshow(display, sync)

        if result == "reset_wifi":
            print("[Service] WiFi reset command received. Re-entering setup mode.")
            continue
        elif result == "restart":
            print("[Service] Restart command received.")
            continue
        elif result == "quit":
            break

        # Check if reset was triggered by button
        if _reset_requested.is_set():
            print("[Service] Button reset triggered. Re-entering setup mode.")
            continue

        # Check if WiFi dropped
        if not is_wifi_connected():
            print("[Service] WiFi dropped. Will re-enter setup mode.")
            continue

    # ── Cleanup ───────────────────────────────────────────────────────────────
    print("[Service] Shutting down...")
    stop_portal()
    stop_hotspot()
    display.quit()
    print("[Service] AuraFrame service stopped.")


# ── Signal Handlers ───────────────────────────────────────────────────────────
def handle_signal(signum, frame):
    print(f"\n[Service] Received signal {signum}. Shutting down...")
    display.running = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


if __name__ == "__main__":
    main()
