#!/usr/bin/env python3
"""
AuraFrame Display Engine
Renders photos fullscreen on a 5-inch HDMI LCD (800x480) using pygame.
Images are displayed preserving their original orientation:
  - Portrait photos → displayed as portrait (pillarboxed with black bars on sides)
  - Landscape photos → displayed as landscape (letterboxed if needed)
  - Scaling always fits within the screen while maintaining aspect ratio.
Works on both Raspberry Pi 3B+ and Raspberry Pi 5.
"""

import os
import sys
import time
import json
import threading
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Try to import pygame (may fail on dev machines)
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[Display] pygame not available — running in headless mode")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
BOOT_DIR = os.path.join(BASE_DIR, "boot")

os.makedirs(CACHE_DIR, exist_ok=True)

# ── Theme Colors (matching the app's warm dark-gold palette) ──────────────────
BG_COLOR = (15, 14, 12)       # #0F0E0C
SURFACE_COLOR = (26, 25, 23)  # #1A1917
GOLD_COLOR = (200, 169, 126)  # #C8A97E
TEXT_COLOR = (245, 242, 238)   # #F5F2EE
DIM_COLOR = (102, 102, 96)    # #666660
BORDER_COLOR = (42, 41, 39)   # #2A2927
SUCCESS_COLOR = (57, 199, 143) # #39C78F
ERROR_COLOR = (255, 112, 112)  # #FF7070

# ── Configuration ─────────────────────────────────────────────────────────────
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
SLIDE_DURATION = 15
POLL_INTERVAL = 30
API_BASE = "https://auraframe-api.vercel.app"
FRAME_ID = ""
API_KEY = ""
FRAME_NAME = "My AuraFrame"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_config():
    """Load config from .env file."""
    global DISPLAY_WIDTH, DISPLAY_HEIGHT, SLIDE_DURATION, POLL_INTERVAL
    global API_BASE, FRAME_ID, API_KEY, FRAME_NAME

    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        env_path = "/opt/auraframe/.env"
    if not os.path.exists(env_path):
        return

    with open(env_path, "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.strip().split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "DISPLAY_WIDTH":
                    DISPLAY_WIDTH = int(val)
                elif key == "DISPLAY_HEIGHT":
                    DISPLAY_HEIGHT = int(val)
                elif key == "SLIDE_DURATION":
                    SLIDE_DURATION = int(val)
                elif key == "POLL_INTERVAL":
                    POLL_INTERVAL = int(val)
                elif key == "API_BASE":
                    API_BASE = val
                elif key == "FRAME_ID":
                    FRAME_ID = val
                elif key == "API_KEY":
                    API_KEY = val
                elif key == "FRAME_NAME":
                    FRAME_NAME = val


# ══════════════════════════════════════════════════════════════════════════════
# Display Renderer
# ══════════════════════════════════════════════════════════════════════════════

class FrameDisplay:
    """Manages the pygame display surface and renders various screens."""

    def __init__(self):
        self.screen = None
        self.running = False
        self.current_state = "boot"  # boot, setup, connecting, empty, slideshow, error
        self._fonts = {}

    def init(self):
        """Initialize pygame display."""
        if not PYGAME_AVAILABLE:
            self.running = True
            return

        pygame.init()
        pygame.mouse.set_visible(False)

        # Try to create fullscreen display
        try:
            self.screen = pygame.display.set_mode(
                (DISPLAY_WIDTH, DISPLAY_HEIGHT),
                pygame.FULLSCREEN | pygame.NOFRAME
            )
        except Exception:
            self.screen = pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT))

        pygame.display.set_caption("AuraFrame")
        self.running = True
        self._clear()

    def _get_font(self, size, bold=False):
        """Cache and return pygame fonts."""
        key = (size, bold)
        if key not in self._fonts:
            path = FONT_BOLD_PATH if bold else FONT_PATH
            try:
                self._fonts[key] = pygame.font.Font(path, size)
            except Exception:
                self._fonts[key] = pygame.font.SysFont("dejavusans", size, bold=bold)
        return self._fonts[key]

    def _clear(self, color=None):
        """Clear screen to background color."""
        if self.screen:
            self.screen.fill(color or BG_COLOR)

    def _draw_centered_text(self, text, y, font_size=16, color=None, bold=False):
        """Draw centered text at the given y coordinate."""
        if not self.screen:
            return
        font = self._get_font(font_size, bold)
        surface = font.render(text, True, color or TEXT_COLOR)
        rect = surface.get_rect(center=(DISPLAY_WIDTH // 2, y))
        self.screen.blit(surface, rect)

    def _draw_logo(self, y_center=120):
        """Draw the AuraFrame logo (gold rounded square with 'A')."""
        if not self.screen:
            return
        # Gold square
        logo_size = 64
        logo_rect = pygame.Rect(0, 0, logo_size, logo_size)
        logo_rect.center = (DISPLAY_WIDTH // 2, y_center)
        pygame.draw.rect(self.screen, GOLD_COLOR, logo_rect, border_radius=16)
        # Letter A
        font = self._get_font(36, bold=True)
        a_surf = font.render("A", True, BG_COLOR)
        a_rect = a_surf.get_rect(center=logo_rect.center)
        self.screen.blit(a_surf, a_rect)

    def _pump_events(self):
        """Process pygame events to prevent freezing."""
        if not PYGAME_AVAILABLE:
            return
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    # ── Screen: Boot Splash ───────────────────────────────────────────────────
    def show_boot(self):
        """Show branded boot splash."""
        self.current_state = "boot"
        self._clear()
        self._draw_logo(160)
        self._draw_centered_text("AuraFrame", 220, font_size=32, color=TEXT_COLOR, bold=True)
        self._draw_centered_text("Starting...", 260, font_size=14, color=DIM_COLOR)
        self._flip()

    # ── Screen: WiFi Setup ────────────────────────────────────────────────────
    def show_setup(self, hotspot_ssid):
        """Show WiFi setup instructions on the frame display."""
        self.current_state = "setup"
        self._clear()
        self._draw_logo(100)
        self._draw_centered_text("AuraFrame", 150, font_size=28, color=TEXT_COLOR, bold=True)

        # Instructions
        self._draw_centered_text("WiFi Setup Required", 210, font_size=20, color=GOLD_COLOR, bold=True)
        self._draw_centered_text("Follow these steps on your phone:", 245, font_size=14, color=DIM_COLOR)

        # Steps
        steps = [
            f"1. Connect to WiFi network: {hotspot_ssid}",
            "2. A setup page will open automatically",
            "3. Select your home WiFi and enter the password",
            "4. Your frame will connect and start showing photos!"
        ]
        y = 285
        for step in steps:
            self._draw_centered_text(step, y, font_size=14, color=TEXT_COLOR)
            y += 30

        # Bottom bar
        pygame.draw.line(self.screen, BORDER_COLOR, (100, 420), (700, 420), 1)
        self._draw_centered_text(f"Hotspot: {hotspot_ssid}  •  Portal: 192.168.4.1", 448, font_size=12, color=DIM_COLOR)

        self._flip()

    # ── Screen: Connecting ────────────────────────────────────────────────────
    def show_connecting(self, ssid):
        """Show 'connecting to WiFi' screen."""
        self.current_state = "connecting"
        self._clear()
        self._draw_logo(140)
        self._draw_centered_text("Connecting to WiFi...", 210, font_size=22, color=GOLD_COLOR, bold=True)
        self._draw_centered_text(f"Network: {ssid}", 250, font_size=16, color=TEXT_COLOR)
        self._draw_centered_text("Please wait...", 290, font_size=14, color=DIM_COLOR)
        self._flip()

    # ── Screen: Connected ─────────────────────────────────────────────────────
    def show_connected(self, ssid):
        """Show 'connected successfully' screen."""
        self._clear()
        self._draw_logo(130)
        self._draw_centered_text("✓ Connected!", 200, font_size=26, color=SUCCESS_COLOR, bold=True)
        self._draw_centered_text(f"WiFi: {ssid}", 240, font_size=16, color=TEXT_COLOR)
        self._draw_centered_text("Open the AuraFrame app to send photos", 290, font_size=14, color=DIM_COLOR)
        self._draw_centered_text("Pair using the PIN code shown in the app", 320, font_size=13, color=DIM_COLOR)
        self._flip()

    def show_pairing(self, pin):
        """Show PIN code and pairing instructions on the frame display."""
        self.current_state = "pairing"
        self._clear()
        self._draw_logo(100)
        self._draw_centered_text("AuraFrame", 150, font_size=28, color=TEXT_COLOR, bold=True)
        self._draw_centered_text("Pair Frame with Mobile App", 210, font_size=20, color=GOLD_COLOR, bold=True)
        self._draw_centered_text("Enter this PIN code in the AuraFrame app on your phone:", 250, font_size=14, color=DIM_COLOR)

        # Draw pairing PIN
        self._draw_centered_text(pin, 320, font_size=48, color=GOLD_COLOR, bold=True)

        self._draw_centered_text("Waiting for connection...", 390, font_size=13, color=DIM_COLOR)

        if self.screen:
            pygame.draw.line(self.screen, BORDER_COLOR, (100, 420), (700, 420), 1)
        self._draw_centered_text(f"Frame: {FRAME_NAME}", 448, font_size=12, color=DIM_COLOR)
        self._flip()

    # ── Screen: No Photos ────────────────────────────────────────────────────
    def show_empty(self):
        """Show 'waiting for photos' screen."""
        self.current_state = "empty"
        self._clear()
        self._draw_logo(130)
        self._draw_centered_text(FRAME_NAME, 185, font_size=24, color=TEXT_COLOR, bold=True)

        # Decorative divider
        pygame.draw.line(self.screen, GOLD_COLOR,
                         (DISPLAY_WIDTH // 2 - 40, 215),
                         (DISPLAY_WIDTH // 2 + 40, 215), 2)

        self._draw_centered_text("No photos yet", 250, font_size=18, color=DIM_COLOR)
        self._draw_centered_text("Open the AuraFrame app on your phone", 290, font_size=14, color=DIM_COLOR)
        self._draw_centered_text("and send your first photo!", 315, font_size=14, color=DIM_COLOR)

        # Animated pulsing dot at bottom
        self._draw_centered_text("● Waiting for photos...", 420, font_size=12, color=GOLD_COLOR)
        self._flip()

    # ── Screen: Display Photo ─────────────────────────────────────────────────
    def show_photo(self, image_path, caption=None, crossfade=True):
        """
        Display a photo on screen, preserving its original orientation.
        Portrait images are displayed as portrait (pillarboxed).
        Landscape images are displayed as landscape (letterboxed if needed).
        """
        self.current_state = "slideshow"
        if not self.screen or not os.path.exists(image_path):
            return

        try:
            # Load the image with Pillow for reliable format handling
            pil_img = Image.open(image_path)
            pil_img = ImageOps.exif_transpose(pil_img)
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")

            img_w, img_h = pil_img.size

            # Draw caption overlay if present (apply to original image first)
            if caption:
                pil_img = self._render_caption(pil_img, caption)

            # If portrait, rotate 90 degrees counter-clockwise so that it fits the landscape screen layout.
            # When the user physically stands the frame vertically, it will appear upright.
            if img_w < img_h:
                pil_img = pil_img.rotate(90, expand=True)
                img_w, img_h = pil_img.size

            # Calculate scale to fit within display while preserving aspect ratio
            scale_w = DISPLAY_WIDTH / img_w
            scale_h = DISPLAY_HEIGHT / img_h
            scale = min(scale_w, scale_h)

            new_w = int(img_w * scale)
            new_h = int(img_h * scale)

            # Resize with high-quality resampling
            pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)


            # Convert PIL image to pygame surface
            img_bytes = pil_img.tobytes()
            py_surface = pygame.image.fromstring(img_bytes, (new_w, new_h), "RGB")

            # Calculate centered position (pillarbox/letterbox)
            x = (DISPLAY_WIDTH - new_w) // 2
            y = (DISPLAY_HEIGHT - new_h) // 2

            # Crossfade effect
            if crossfade:
                self._crossfade_to(py_surface, x, y)
            else:
                self._clear()
                self.screen.blit(py_surface, (x, y))
                self._flip()

        except Exception as e:
            print(f"[Display] Error rendering {image_path}: {e}")

    def _render_caption(self, pil_img, caption_text):
        """Render a semi-transparent caption bar at the bottom of the image."""
        width, height = pil_img.size
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Caption bar height: 16% of image
        bar_h = int(height * 0.16)
        bar_y = height - bar_h

        # Semi-transparent dark bar
        draw.rectangle([(0, bar_y), (width, height)], fill=(15, 14, 12, 180))
        # Gold accent line
        draw.line([(0, bar_y), (width, bar_y)], fill=(200, 169, 126, 220), width=2)

        # Font
        font_size = max(14, int(height * 0.045))
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except Exception:
            font = ImageFont.load_default()

        text = f'"{caption_text}"'
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(text, font=font)

        tx = (width - tw) // 2
        ty = bar_y + (bar_h - th) // 2

        draw.text((tx, ty), text, font=font, fill=(245, 242, 238, 240))

        composite = Image.alpha_composite(pil_img.convert("RGBA"), overlay)
        return composite.convert("RGB")

    def _crossfade_to(self, new_surface, x, y, steps=12, duration_ms=400):
        """Smooth crossfade transition to a new image."""
        # Capture current screen
        old_screen = self.screen.copy()
        new_screen = pygame.Surface((DISPLAY_WIDTH, DISPLAY_HEIGHT))
        new_screen.fill(BG_COLOR)
        new_screen.blit(new_surface, (x, y))

        step_time = duration_ms / steps / 1000.0

        for i in range(steps + 1):
            alpha = int(255 * i / steps)
            self.screen.blit(old_screen, (0, 0))
            new_screen.set_alpha(alpha)
            self.screen.blit(new_screen, (0, 0))
            pygame.display.flip()
            self._pump_events()
            time.sleep(step_time)

        # Final full-opacity render
        self._clear()
        self.screen.blit(new_surface, (x, y))
        self._flip()

    def _flip(self):
        """Update the display."""
        if self.screen:
            pygame.display.flip()

    def quit(self):
        """Clean shutdown."""
        self.running = False
        if PYGAME_AVAILABLE:
            pygame.quit()


# ══════════════════════════════════════════════════════════════════════════════
# Cloud Photo Synchronization
# ══════════════════════════════════════════════════════════════════════════════

class PhotoSync:
    """Synchronizes photos from the AuraFrame cloud API."""

    def __init__(self):
        self.photos = []  # List of {"id": ..., "path": ..., "caption": ...}
        self.last_sync = 0
        self.slideshow_enabled = True


    def sync(self):
        """Poll the cloud API for the frame's photo queue."""
        if not FRAME_ID or not API_KEY:
            print("[Sync] No FRAME_ID or API_KEY configured. Skipping sync.")
            return

        print("[Sync] Polling cloud for photo updates...")
        url = f"{API_BASE}/frames/{FRAME_ID}/images"
        headers = {"Authorization": f"Bearer {API_KEY}"}

        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"[Sync] API returned {res.status_code}")
                return

            data = res.json()
            images = data.get("images", [])
            active_ids = set()

            for img in images:
                img_id = img.get("id", "")
                img_url = img.get("url", "")
                caption = img.get("caption", None)
                if not img_id or not img_url:
                    continue

                active_ids.add(img_id)
                local_path = os.path.join(CACHE_DIR, f"{img_id}.jpg")

                if not os.path.exists(local_path):
                    print(f"[Sync] Downloading: {img_id}")
                    try:
                        dl = requests.get(img_url, timeout=30)
                        if dl.status_code == 200:
                            with open(local_path, "wb") as f:
                                f.write(dl.content)
                        else:
                            print(f"[Sync] Download failed for {img_id}: {dl.status_code}")
                            continue
                    except Exception as e:
                        print(f"[Sync] Download error: {e}")
                        continue

            # Build photo list
            self.photos = []
            for img in images:
                img_id = img.get("id", "")
                caption = img.get("caption", None)
                local_path = os.path.join(CACHE_DIR, f"{img_id}.jpg")
                if os.path.exists(local_path):
                    self.photos.append({
                        "id": img_id,
                        "path": local_path,
                        "caption": caption
                    })

            # Prune old cached files
            for filename in os.listdir(CACHE_DIR):
                if filename.endswith(".jpg"):
                    file_id = filename.replace(".jpg", "")
                    if file_id not in active_ids:
                        try:
                            os.remove(os.path.join(CACHE_DIR, filename))
                            print(f"[Sync] Pruned: {filename}")
                        except OSError:
                            pass

            self.slideshow_enabled = data.get("slideshowEnabled", True)
            self.last_sync = time.time()
            print(f"[Sync] Complete. {len(self.photos)} photos in queue. Slideshow: {self.slideshow_enabled}")

        except Exception as e:
            print(f"[Sync] Network error: {e}")

            # Load from cache if offline
            if not self.photos:
                self._load_from_cache()

    def _load_from_cache(self):
        """Load photos from local cache when offline."""
        self.photos = []
        if os.path.exists(CACHE_DIR):
            for filename in sorted(os.listdir(CACHE_DIR)):
                if filename.endswith(".jpg"):
                    self.photos.append({
                        "id": filename.replace(".jpg", ""),
                        "path": os.path.join(CACHE_DIR, filename),
                        "caption": None
                    })
        print(f"[Sync] Loaded {len(self.photos)} photos from cache (offline mode)")

    def check_commands(self):
        """Poll the cloud API for pending commands (reset, restart, etc.)."""
        if not FRAME_ID or not API_KEY:
            return None
        try:
            url = f"{API_BASE}/frames/{FRAME_ID}/command"
            headers = {"Authorization": f"Bearer {API_KEY}"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                cmd = data.get("command")
                if cmd:
                    print(f"[Sync] Received command: {cmd}")
                    # Acknowledge the command
                    requests.delete(url, headers=headers, timeout=10)
                    return cmd
        except Exception:
            pass
        return None

    def send_heartbeat(self):
        """Send heartbeat status to the cloud API."""
        if not FRAME_ID or not API_KEY:
            return
        try:
            from wifi_portal import get_current_wifi_info
            wifi_info = get_current_wifi_info()
        except Exception:
            wifi_info = {}

        try:
            url = f"{API_BASE}/frames/{FRAME_ID}/heartbeat"
            headers = {"Authorization": f"Bearer {API_KEY}"}
            payload = {
                "status": "online",
                "photoCount": len(self.photos),
                "wifiSsid": wifi_info.get("ssid", ""),
                "localIp": wifi_info.get("ip", ""),
                "uptime": int(time.time()),
            }
            requests.post(url, json=payload, headers=headers, timeout=10)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# Slideshow Runner
# ══════════════════════════════════════════════════════════════════════════════

def run_slideshow(display, sync):
    """Main slideshow loop — called from the service coordinator."""
    load_config()
    photo_index = 0
    current_photo_id = None
    last_poll = 0
    last_heartbeat = 0
    heartbeat_interval = 120  # Every 2 minutes

    # Initial sync
    sync.sync()

    while display.running:
        now = time.time()

        # Periodic cloud sync
        if now - last_poll >= POLL_INTERVAL:
            sync.sync()
            last_poll = now

            # Check for remote commands
            cmd = sync.check_commands()
            if cmd == "reset_wifi":
                print("[Slideshow] Received reset_wifi command. Exiting to main service.")
                return "reset_wifi"
            elif cmd == "restart":
                print("[Slideshow] Received restart command.")
                return "restart"

        # Periodic heartbeat
        if now - last_heartbeat >= heartbeat_interval:
            sync.send_heartbeat()
            last_heartbeat = now

        # Display photos
        if sync.photos:
            if not getattr(sync, "slideshow_enabled", True):
                # Show only the latest image
                photo = sync.photos[-1]
                if photo["id"] != current_photo_id:
                    display.show_photo(
                        photo["path"],
                        caption=photo.get("caption"),
                        crossfade=(current_photo_id is not None)
                    )
                    current_photo_id = photo["id"]
                
                # Wait and pump events periodically
                wait_start = time.time()
                while time.time() - wait_start < 2 and display.running:
                    display._pump_events()
                    time.sleep(0.2)
            else:
                if photo_index >= len(sync.photos):
                    photo_index = 0

                photo = sync.photos[photo_index]
                display.show_photo(
                    photo["path"],
                    caption=photo.get("caption"),
                    crossfade=(current_photo_id is not None)
                )
                current_photo_id = photo["id"]
                photo_index += 1

                # Wait for slide duration, pumping events periodically
                wait_start = time.time()
                while time.time() - wait_start < SLIDE_DURATION and display.running:
                    display._pump_events()
                    time.sleep(0.2)
        else:
            display.show_empty()
            current_photo_id = None
            # Wait and retry
            wait_start = time.time()
            while time.time() - wait_start < 10 and display.running:
                display._pump_events()
                time.sleep(0.2)


    return "quit"
