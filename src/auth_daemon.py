#!/usr/bin/env python3
"""GitHub device-flow automation daemon (macOS).

Two entry points:
  * HTTP POST /auth/start  - called by the shell precmd hook when a device
    code appears in the clipboard.
  * Cmd+G hotkey           - OCRs the current screen with Apple Vision and
    finds a code near "one-time code" / GitHub context.

Both funnel into `_handle_device_code`, which drives `agent-browser` using
a stored session (~/.config/auth-daemon/github-auth.json).
"""

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

# Load .env at repo root (sets vars like AGENT_BROWSER_HEADED=true for debugging)
_env_path = REPO_ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LOG_DIR = Path.home() / "Library" / "Logs" / "GitHub Auth Agent"
LOG_PATH = LOG_DIR / "auth-daemon.log"
STATE_DIR = Path.home() / ".config" / "auth-daemon"
STATE_FILE = STATE_DIR / "github-auth.json"
PREFS_FILE = STATE_DIR / "prefs.json"


def load_prefs() -> dict:
    try:
        return json.loads(PREFS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_prefs(prefs: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    PREFS_FILE.write_text(json.dumps(prefs, indent=2))
_NOTIFIER_REL = "Contents/MacOS/terminal-notifier"
NOTIFIER_BIN = next(
    (p for p in (
        Path("/Applications/GitHubAuthAgent.app") / _NOTIFIER_REL,
        REPO_ROOT / "assets" / "GitHubAuthAgent.app" / _NOTIFIER_REL,
    ) if p.exists()),
    None,
)

DEVICE_CODE_RE = re.compile(r"[A-Z0-9]{4}-[A-Z0-9]{4}")
DAEMON_PORT = int(os.environ.get("AUTH_DAEMON_PORT", "8000"))


def _ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def _notify(title: str, subtitle: str, message: str) -> None:
    """Fire a macOS notification via the bundled GitHubAuthAgent.app helper.

    The helper is a re-skinned terminal-notifier bundle with its own bundle ID
    (com.livio.github-auth-agent) and a GitHub-mark app icon, so notifications
    appear from "GitHub Auth Agent" with the right icon. Prefers the installed
    copy at /Applications/GitHubAuthAgent.app and falls back to the in-repo
    copy for development. No-op if neither path exists.
    """
    if NOTIFIER_BIN is None:
        return
    try:
        subprocess.Popen(
            [
                str(NOTIFIER_BIN),
                "-title", title,
                "-subtitle", subtitle,
                "-message", message,
                "-sound", "default",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass  # notifications are best-effort; never fail the auth flow over a UI ping


def _failure_reason(url: str) -> str:
    """Extract the `reason=` query value from a GitHub device-flow failure URL."""
    try:
        return parse_qs(urlparse(url).query).get("reason", ["unknown"])[0]
    except Exception:
        return "unknown"


class ReuseAddrHTTPServer(HTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        if self.path == "/auth/start":
            self._handle_auth_start(body)
        else:
            self._json(404, {"error": "not found"})

    def _handle_auth_start(self, body: str) -> None:
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON"})
            return

        service = data.get("service", "").lower()
        device_code = data.get("device_code", "").strip()

        if service != "github":
            self._json(400, {"error": "only 'github' is supported"})
            return
        if not DEVICE_CODE_RE.fullmatch(device_code):
            self._json(400, {"error": "device_code must match XXXX-XXXX"})
            return

        threading.Thread(
            target=self.server.auth_daemon._handle_device_code,
            args=(service, device_code),
            daemon=True,
        ).start()

        self._json(200, {
            "status": "started",
            "service": service,
            "device_code": device_code,
            "timestamp": datetime.now().isoformat(),
        })

    def _json(self, status: int, payload: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # silence default HTTP access log
        pass


class AuthDaemon:
    def __init__(self):
        _ensure_dirs()
        self._setup_logging()
        logging.info("GitHub Auth Agent starting")

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(LOG_PATH),
                logging.StreamHandler(sys.stdout),
            ],
        )

    def _handle_device_code(self, service: str, code: str) -> None:
        """Drive agent-browser through the GitHub device-code page with the saved session."""
        if service != "github":
            logging.warning(f"Unsupported service: {service}")
            return
        if not STATE_FILE.exists():
            logging.error("No GitHub session at %s; cannot auto-authenticate.", STATE_FILE)
            _notify("GitHub Auth Agent failed", "No saved session", f"Missing {STATE_FILE}")
            return

        logging.info(f"Starting GitHub auth with code: {code}")
        _notify("GitHub Auth Agent", "Code detected", f"Authenticating with code {code}…")

        def ab(*args, timeout=20):
            # Find agent-browser in PATH or use direct path
            agent_browser = shutil.which("agent-browser") or "/opt/homebrew/bin/agent-browser"
            r = subprocess.run(
                [agent_browser, *args],
                capture_output=True, text=True, timeout=timeout, env={**os.environ},
            )
            out = (r.stdout or r.stderr).strip()
            limit = 500 if args[0] == "snapshot" else 120
            logging.info(f"ab {args[0]}: {out[:limit]}")
            return r.returncode, r.stdout.strip()

        try:
            # agent-browser's --state is only read at daemon start, so kill any
            # running instance first to force it to reload the session file.
            subprocess.run(["pkill", "-9", "-f", "agent-browser-darwin"], capture_output=True)
            for _ in range(20):
                time.sleep(0.1)
                if subprocess.run(["pgrep", "-f", "agent-browser-darwin"], capture_output=True).returncode != 0:
                    break

            def navigate_and_fill(chars, open_args=None):
                if open_args:
                    ab(*open_args, timeout=15)
                ab("wait", "--fn", "document.readyState === 'complete'", timeout=20)
                _, url = ab("get", "url", timeout=5)
                if "select_account" in url:
                    _, sel_snap = ab("snapshot", "-i", timeout=10)
                    cont_ref = re.search(r'button "Continue as [^"]*" \[ref=(e\d+)\]', sel_snap) \
                        or re.search(r'button "Continue" \[ref=(e\d+)\]', sel_snap)
                    if cont_ref:
                        ab("click", f"@{cont_ref.group(1)}", timeout=10)
                    else:
                        logging.warning("Could not find Continue button in snapshot")
                ab("wait", "--text", "Authorize your device", timeout=20)
                _, snap = ab("snapshot", "-i", timeout=10)
                textbox_refs = re.findall(r'textbox "User code \d+" \[ref=(e\d+)\]', snap)
                logging.info(f"Filling code chars: {list(chars)} into {len(textbox_refs)} boxes")
                if len(textbox_refs) >= 8:
                    for i, (char, ref) in enumerate(zip(chars, textbox_refs)):
                        ab("click", f"@{ref}", timeout=5)
                        ab("keyboard", "type", char, timeout=5)
                        logging.info(f"  box {i}: ref={ref} char={char!r}")
                else:
                    logging.warning(f"Found {len(textbox_refs)} textboxes, expected 8")
                    if textbox_refs:
                        ab("click", f"@{textbox_refs[0]}", timeout=5)
                    ab("keyboard", "type", "".join(chars), timeout=10)
                ab("press", "Enter", timeout=5)
                ab("wait", "--fn", "window.location.pathname !== '/login/device'", timeout=30)
                ab("wait", "--fn", "document.readyState === 'complete'", timeout=15)
                _, result_url = ab("get", "url", timeout=5)
                logging.info(f"Post-submit URL: {result_url}")
                return result_url

            headed_flag = ("--headed",) if not load_prefs().get("headless", True) else ()
            code_chars = list(code.replace("-", ""))
            cur_url = navigate_and_fill(
                code_chars,
                open_args=("--state", str(STATE_FILE), *headed_flag,
                           "open", "https://github.com/login/device"),
            )

            if "failure" in cur_url or "not_found" in cur_url:
                # OCR commonly confuses O and 0; one retry with them swapped.
                swapped = ['0' if c == 'O' else 'O' if c == '0' else c for c in code_chars]
                if swapped != code_chars:
                    logging.warning(f"not_found - retrying with O<->0 swap: {swapped}")
                    cur_url = navigate_and_fill(
                        swapped, open_args=("open", "https://github.com/login/device"),
                    )
                if "failure" in cur_url or "not_found" in cur_url:
                    reason = _failure_reason(cur_url)
                    logging.error(f"GitHub device code rejected - reason: {reason}")
                    _notify("GitHub Auth Agent failed", f"reason: {reason}", f"Code {code} was rejected.")
                    return

            ab("scroll", "down", "500", timeout=5)
            time.sleep(0.5)
            _, snap3 = ab("snapshot", "-i", timeout=10)
            auth_ref = re.search(r'button "Authorize[^"]*" \[ref=(e\d+)\]', snap3)
            if auth_ref:
                ab("click", f"@{auth_ref.group(1)}", timeout=10)
                logging.info("Clicked Authorize button")
            else:
                logging.warning(f"Authorize button not found - URL: {cur_url}")
                logging.info(f"Snapshot: {snap3[:300]}")
                ab("press", "Enter", timeout=5)

            ab("wait", "--fn", "window.location.pathname === '/login/device/success'", timeout=30)
            logging.info("GitHub auth flow completed successfully")
            _notify("GitHub Auth Agent", "Success", f"Authenticated with code {code}.")
            ab("close", "--all", timeout=10)

        except subprocess.TimeoutExpired:
            logging.error("agent-browser command timed out")
            _notify("GitHub Auth Agent failed", "Timeout", "agent-browser command timed out.")
        except Exception as e:
            logging.error(f"GitHub auth error: {e}")
            _notify("GitHub Auth Agent failed", "Error", str(e)[:200])
            import traceback
            logging.error(traceback.format_exc())

    def _listen_for_hotkey(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as e:
            logging.error(f"pynput missing ({e}); hotkey disabled.")
            return

        logging.info("Hotkey listener active - press Cmd+G to OCR-scan the screen")
        cmd_held = False
        shift_held = False
        last_trigger = [0.0]

        CMD_KEYS = (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r)
        SHIFT_KEYS = (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r)

        def trigger():
            now = time.time()
            if now - last_trigger[0] < 1.0:
                return
            last_trigger[0] = now
            logging.info("[hotkey] Cmd+G - scanning screen")
            _notify("GitHub Auth Agent", "Hotkey detected", "Scanning screen for device code…")
            threading.Thread(target=self._scan_screen_with_vision_framework, daemon=True).start()

        def is_g_key(key) -> bool:
            return getattr(key, "char", None) in ("g", "G") or getattr(key, "vk", None) == 5

        def on_press(key):
            nonlocal cmd_held, shift_held
            if key in CMD_KEYS:
                cmd_held = True
            elif key in SHIFT_KEYS:
                shift_held = True
            elif cmd_held and not shift_held and is_g_key(key):
                trigger()

        def on_release(key):
            nonlocal cmd_held, shift_held
            if key in CMD_KEYS:
                cmd_held = False
            elif key in SHIFT_KEYS:
                shift_held = False

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    def _scan_screen_with_vision_framework(self) -> None:
        """Capture the screen with the cursor, OCR a 3x4 grid in parallel, look for a code."""
        try:
            import concurrent.futures
            import io
            import numpy as np
            from Foundation import NSArray, NSData, NSEvent, NSMouseInRect, NSScreen
            from PIL import Image
            import Quartz
            from Vision import VNImageRequestHandler, VNRecognizeTextRequest

            mouse_loc = NSEvent.mouseLocation()
            target_display_id = next(
                (s.deviceDescription()["NSScreenNumber"]
                 for s in NSScreen.screens() if NSMouseInRect(mouse_loc, s.frame(), False)),
                Quartz.CGMainDisplayID(),
            )

            image_ref = Quartz.CGDisplayCreateImage(int(target_display_id))
            img_w = Quartz.CGImageGetWidth(image_ref)
            img_h = Quartz.CGImageGetHeight(image_ref)
            color_space = Quartz.CGColorSpaceCreateDeviceRGB()
            bitmap_context = Quartz.CGBitmapContextCreate(
                None, img_w, img_h, 8, img_w * 4,
                color_space, Quartz.kCGImageAlphaNoneSkipFirst,
            )
            Quartz.CGContextDrawImage(bitmap_context, Quartz.CGRectMake(0, 0, img_w, img_h), image_ref)
            bitmap_image_ref = Quartz.CGBitmapContextCreateImage(bitmap_context)
            data_provider = Quartz.CGImageGetDataProvider(bitmap_image_ref)
            pixel_data = Quartz.CGDataProviderCopyData(data_provider)
            pixels = np.frombuffer(pixel_data, dtype=np.uint8).reshape((img_h, img_w, 4))[:, :, [2, 1, 0]]
            screenshot = Image.fromarray(pixels)
            screenshot.load()
            logging.info(f"Captured screenshot: {screenshot.size}")

            cols, rows = 3, 4
            grid = {
                f"R{r}C{c}": screenshot.crop((
                    c * img_w // cols, r * img_h // rows,
                    (c + 1) * img_w // cols, (r + 1) * img_h // rows,
                )).copy()
                for r in range(rows) for c in range(cols)
            }

            def ocr_tile(name, tile):
                buf = io.BytesIO()
                tile.save(buf, format="PNG")
                ns_data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
                req = VNRecognizeTextRequest.new()
                req.setRecognitionLanguages_(["en"])
                VNImageRequestHandler.alloc().initWithData_options_(ns_data, None) \
                    .performRequests_error_(NSArray.arrayWithObject_(req), None)
                return name, "\n".join(c.string() for o in req.results() for c in o.topCandidates_(1))

            with concurrent.futures.ThreadPoolExecutor() as ex:
                tile_texts = dict(ex.map(lambda kv: ocr_tile(*kv), grid.items()))

            # Two passes, narrowest context first: a XXXX-XXXX match only counts
            # when it's near "one-time code" or, failing that, a GitHub keyword.
            # Otherwise random alphanumeric strings (PRs, hashes) would trigger.
            device_code = None
            for required in (["one-time code"], ["github.com/login/device", "login/device", "github"]):
                for name, text in tile_texts.items():
                    lower = text.lower()
                    if not any(kw in lower for kw in required):
                        continue
                    m = DEVICE_CODE_RE.search(text)
                    if m:
                        device_code = m.group(0)
                        logging.info(f"Found device code in {name}: {device_code}")
                        logging.info(f"  context: {text[:300]}")
                        break
                if device_code:
                    break

            if not device_code:
                logging.warning("No device code found on screen")
                _notify("GitHub Auth Agent", "No code found", "Could not detect a device code on the visible screen.")
                return

            self._handle_device_code("github", device_code)

        except Exception as e:
            logging.error(f"Vision OCR error: {e}")
            import traceback
            logging.error(traceback.format_exc())

    def start_server(self, port: int = DAEMON_PORT) -> None:
        server = ReuseAddrHTTPServer(("127.0.0.1", port), AuthHandler)
        server.auth_daemon = self
        logging.info(f"Auth daemon listening on 127.0.0.1:{port}")
        server.serve_forever()

    def run(self) -> None:
        threading.Thread(target=self.start_server, daemon=True).start()
        try:
            self._listen_for_hotkey()
        except KeyboardInterrupt:
            logging.info("GitHub Auth Agent stopped")
            sys.exit(0)


def main():
    AuthDaemon().run()


if __name__ == "__main__":
    main()
