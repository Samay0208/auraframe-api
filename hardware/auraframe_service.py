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
