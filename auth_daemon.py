#!/usr/bin/env python3
"""
Multi-service OAuth/device-flow automation daemon.
Watches terminal output, extracts auth codes, orchestrates browser automation.
Supports: macOS, Linux, Windows
"""

import os
import sys
import json
import time
import socket
import logging
import re
import subprocess
import threading
import platform as platform_module
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
import hashlib
import pickle

# Core daemon configuration
DAEMON_NAME = "auth-daemon"
CACHE_DIR = Path.home() / ".cache" / "auth-daemon"
SOCKET_PATH = Path.home() / ".cache" / "auth-daemon.sock"
LOG_PATH = CACHE_DIR / "daemon.log"

# Auth code patterns for different services
AUTH_PATTERNS = {
    "github": {
        "device_code": r"[A-Z0-9]{4}-[A-Z0-9]{4}",
        "url": "https://github.com/login/device",
    },
    "google": {
        "device_code": r"[A-Z0-9]{8,}",
        "url": "https://google.com/device",
    },
    "generic_oauth": {
        "url_pattern": r"(http://localhost:\d+/callback|https://\S+/auth/callback)",
    },
}

# Session cache format
@dataclass
class CachedSession:
    service: str
    token: str
    refresh_token: Optional[str]
    expires_at: float
    created_at: float

    def is_valid(self) -> bool:
        return time.time() < self.expires_at

    def to_dict(self) -> dict:
        return asdict(self)


class AccessibilityAPI:
    """Base class for platform-specific UI automation."""

    @staticmethod
    def get_active_app() -> Optional[str]:
        """Get name of active application. Override per platform."""
        return None

    @staticmethod
    def click_button(button_text: str, app_name: Optional[str] = None) -> bool:
        """Click a button by text."""
        logging.warning("click_button not implemented on this platform")
        return False

    @staticmethod
    def type_text(text: str) -> bool:
        """Type text in active window."""
        logging.warning("type_text not implemented on this platform")
        return False

    @staticmethod
    def open_url(url: str, browser: str = "Chrome") -> bool:
        """Open URL in browser."""
        logging.warning("open_url not implemented on this platform")
        return False


class macOSAccessibilityAPI(AccessibilityAPI):
    """macOS Accessibility API via osascript."""

    @staticmethod
    def get_active_app() -> Optional[str]:
        """Get name of active application."""
        try:
            cmd = 'osascript -e "tell application \\"System Events\\" to name of first application process where frontmost is true"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception as e:
            logging.error(f"Failed to get active app: {e}")
            return None

    @staticmethod
    def click_button(button_text: str, app_name: Optional[str] = None) -> bool:
        """Click a button by text in an application."""
        try:
            if not app_name:
                app_name = macOSAccessibilityAPI.get_active_app()

            script = f'''
tell application "System Events"
    tell process "{app_name}"
        click button "{button_text}"
    end tell
end tell
'''
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Failed to click button: {e}")
            return False

    @staticmethod
    def type_text(text: str) -> bool:
        """Type text in the active window."""
        try:
            script = f'tell application "System Events" to keystroke "{text}"'
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Failed to type text: {e}")
            return False

    @staticmethod
    def open_url(url: str, browser: str = "Chrome") -> bool:
        """Open URL in specified browser."""
        try:
            script = f'''
tell application "{browser}"
    activate
    open location "{url}"
end tell
'''
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Failed to open URL: {e}")
            return False


class LinuxAccessibilityAPI(AccessibilityAPI):
    """Linux UI automation via xdotool and xdg-open."""

    @staticmethod
    def _check_xdotool() -> bool:
        """Check if xdotool is available."""
        try:
            subprocess.run(["xdotool", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    @staticmethod
    def get_active_app() -> Optional[str]:
        """Get name of active window."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logging.error(f"Failed to get active app: {e}")
        return None

    @staticmethod
    def click_button(button_text: str, app_name: Optional[str] = None) -> bool:
        """Click a button using xdotool (searches for text on screen)."""
        if not LinuxAccessibilityAPI._check_xdotool():
            logging.error("xdotool not installed. Install: sudo apt install xdotool")
            return False

        try:
            # Search for button text using xdotool search (requires window focus)
            # Alternative: use OCR or pyautogui for fallback
            result = subprocess.run(
                ["xdotool", "search", "--name", button_text, "windowactivate"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Press Tab/Enter to focus and click
                subprocess.run(["xdotool", "key", "Tab", "Return"], timeout=2)
                return True

            # Fallback: use keyboard to find and activate button
            logging.warning(f"Could not find button '{button_text}', using keyboard navigation")
            subprocess.run(["xdotool", "key", "Tab", "Return"], timeout=2)
            return True

        except Exception as e:
            logging.error(f"Failed to click button: {e}")
            return False

    @staticmethod
    def type_text(text: str) -> bool:
        """Type text using xdotool."""
        if not LinuxAccessibilityAPI._check_xdotool():
            return False

        try:
            # Escape special characters for xdotool
            result = subprocess.run(
                ["xdotool", "type", "--", text], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Failed to type text: {e}")
            return False

    @staticmethod
    def open_url(url: str, browser: str = "Chrome") -> bool:
        """Open URL using xdg-open or browser command."""
        try:
            # Map common browser names to commands
            browser_commands = {
                "Chrome": "google-chrome",
                "Google Chrome": "google-chrome",
                "Chromium": "chromium",
                "Firefox": "firefox",
                "Safari": "safari",  # Less common on Linux
            }

            # Try specific browser first
            cmd = browser_commands.get(browser, browser.lower())
            try:
                subprocess.Popen([cmd, url])
                time.sleep(1)
                return True
            except FileNotFoundError:
                pass

            # Fallback to xdg-open (uses default browser)
            subprocess.Popen(["xdg-open", url])
            time.sleep(1)
            return True

        except Exception as e:
            logging.error(f"Failed to open URL: {e}")
            return False


class WindowsAccessibilityAPI(AccessibilityAPI):
    """Windows UI automation via pyautogui and os.startfile."""

    @staticmethod
    def _check_pyautogui() -> bool:
        """Check if pyautogui is available."""
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    @staticmethod
    def click_button(button_text: str, app_name: Optional[str] = None) -> bool:
        """Click using pyautogui (searches screen for text)."""
        try:
            import pyautogui
            # This is a simplified version; full implementation would need OCR
            # For now, use keyboard navigation
            pyautogui.press("tab")
            time.sleep(0.2)
            pyautogui.press("enter")
            return True
        except Exception as e:
            logging.error(f"Failed to click button: {e}")
            return False

    @staticmethod
    def type_text(text: str) -> bool:
        """Type text using pyautogui."""
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.05)
            return True
        except Exception as e:
            logging.error(f"Failed to type text: {e}")
            return False

    @staticmethod
    def open_url(url: str, browser: str = "Chrome") -> bool:
        """Open URL using os.startfile."""
        try:
            os.startfile(url)
            time.sleep(1)
            return True
        except Exception as e:
            logging.error(f"Failed to open URL: {e}")
            return False


class TerminalWatcher:
    """Watch terminal output for auth codes."""

    def __init__(self):
        self.patterns = AUTH_PATTERNS
        self.callbacks: Dict[str, Callable] = {}

    def register_callback(self, service: str, callback: Callable) -> None:
        """Register callback for when service code is detected."""
        self.callbacks[service] = callback

    def watch_tty(self, tty_path: str) -> None:
        """Watch a TTY device for auth codes."""
        try:
            with open(tty_path, "r") as f:
                for line in f:
                    self._check_line(line)
        except Exception as e:
            logging.error(f"Failed to watch TTY: {e}")

    def _check_line(self, line: str) -> None:
        """Check line for auth codes."""
        for service, pattern_info in self.patterns.items():
            if "device_code" in pattern_info:
                match = re.search(pattern_info["device_code"], line)
                if match:
                    code = match.group(0)
                    logging.info(f"Detected {service} code: {code}")
                    if service in self.callbacks:
                        self.callbacks[service](code, pattern_info.get("url"))


class SessionManager:
    """Cache and manage OAuth sessions."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sessions: Dict[str, CachedSession] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached sessions from disk."""
        cache_file = self.cache_dir / "sessions.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    self.sessions = pickle.load(f)
            except Exception as e:
                logging.warning(f"Failed to load session cache: {e}")

    def _save_cache(self) -> None:
        """Save sessions to disk."""
        cache_file = self.cache_dir / "sessions.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(self.sessions, f)
        except Exception as e:
            logging.error(f"Failed to save session cache: {e}")

    def store(self, service: str, token: str, refresh_token: Optional[str] = None, expires_in: int = 3600) -> None:
        """Store a session."""
        expires_at = time.time() + expires_in
        session = CachedSession(
            service=service,
            token=token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            created_at=time.time(),
        )
        self.sessions[service] = session
        self._save_cache()
        logging.info(f"Cached session for {service}")

    def get(self, service: str) -> Optional[CachedSession]:
        """Get a valid session."""
        session = self.sessions.get(service)
        if session and session.is_valid():
            return session
        return None

    def clear(self, service: str) -> None:
        """Clear a cached session."""
        if service in self.sessions:
            del self.sessions[service]
            self._save_cache()


class AuthHandler(BaseHTTPRequestHandler):
    """HTTP handler for auth daemon API."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length else ""

        if self.path == "/auth/start":
            self._handle_auth_start(body)
        elif self.path == "/session/get":
            self._handle_session_get(body)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_auth_start(self, body: str) -> None:
        """Start an auth flow."""
        try:
            data = json.loads(body) if body else {}
            service = data.get("service", "").lower()

            if not service:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "service required"}).encode())
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "status": "started",
                        "service": service,
                        "timestamp": datetime.now().isoformat(),
                    }
                ).encode()
            )
        except Exception as e:
            self.send_response(500)
            self.end_headers()

    def _handle_session_get(self, body: str) -> None:
        """Get cached session."""
        try:
            data = json.loads(body) if body else {}
            service = data.get("service", "").lower()

            session = self.server.session_manager.get(service)
            if session:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(session.to_dict()).encode())
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "session not found"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP logs."""
        pass


def get_accessibility_api() -> AccessibilityAPI:
    """Get platform-specific accessibility API."""
    system = platform_module.system()

    if system == "Darwin":  # macOS
        return macOSAccessibilityAPI()
    elif system == "Linux":
        return LinuxAccessibilityAPI()
    elif system == "Windows":
        return WindowsAccessibilityAPI()
    else:
        logging.warning(f"Unknown platform: {system}, using base API")
        return AccessibilityAPI()


class AuthDaemon:
    """Main auth daemon process."""

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._setup_logging()

        system = platform_module.system()
        logging.info(f"Auth daemon starting on {system}")

        self.session_manager = SessionManager(CACHE_DIR)
        self.accessibility_api = get_accessibility_api()
        self.terminal_watcher = TerminalWatcher()

        # Register callbacks
        self.terminal_watcher.register_callback("github", self._handle_github_auth)

        logging.info(f"Auth daemon initialized on {system}")

    def _setup_logging(self) -> None:
        """Configure logging."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(LOG_PATH),
                logging.StreamHandler(sys.stdout),
            ],
        )

    def _handle_github_auth(self, code: str, url: str) -> None:
        """Handle GitHub device flow auth."""
        logging.info(f"Starting GitHub auth with code: {code}")

        # Open browser to auth URL
        self.accessibility_api.open_url(url)
        time.sleep(1)

        # Type device code
        self.accessibility_api.type_text(code)
        time.sleep(0.5)

        # Click authorize button
        self.accessibility_api.click_button("Authorize")
        logging.info("GitHub auth flow initiated")

    def start_server(self, port: int = 8000) -> None:
        """Start HTTP API server."""
        server = HTTPServer(("127.0.0.1", port), AuthHandler)
        server.session_manager = self.session_manager

        logging.info(f"Auth daemon server listening on port {port}")
        server.serve_forever()

    def run(self) -> None:
        """Run daemon in background."""
        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()

        logging.info("Auth daemon running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Auth daemon stopped")
            sys.exit(0)


if __name__ == "__main__":
    daemon = AuthDaemon()
    daemon.run()
