# Auth Daemon

Multi-service OAuth/device-flow automation daemon. Automatically orchestrates browser-based authentication flows for GitHub, Google, Anthropic, OpenAI, Slack, Linear, and Atlassian.

**Supported Platforms**: macOS, Linux, Windows

## Architecture

```
Terminal Output Watcher
    ↓
Device Code Regex Extractor
    ↓
Browser Automation Controller (Accessibility API)
    ↓
Service-Specific Auth Handlers
    ↓
Session Cache Manager
    ↓
HTTP API Server (local socket)
```

## Features

- **Terminal Watching**: Monitors terminal output for device codes via regex
- **Browser Automation**: Uses macOS Accessibility API for UI automation (no Puppeteer/Playwright)
- **Multi-Service Support**: GitHub, Google, Anthropic, OpenAI, Slack, Linear, Atlassian
- **Session Caching**: Persistently caches valid OAuth tokens
- **Browser Agnostic**: Works with Chrome, Safari, Firefox
- **Local API**: HTTP server on localhost:8000 for programmatic access
- **Daemon Mode**: Runs as background process

## Installation

### Prerequisites

**macOS:**
- macOS 10.14+
- Python 3.8+
- System Preferences → Security & Privacy → Accessibility: Grant access to Terminal/IDE

**Linux:**
- Python 3.8+
- `xdotool` (for UI automation)
  - Ubuntu/Debian: `sudo apt install xdotool`
  - Fedora: `sudo dnf install xdotool`
  - Arch: `sudo pacman -S xdotool`

**Windows:**
- Python 3.8+
- Optional: `pyautogui` for better automation (`pip install pyautogui`)

### From Source

```bash
cd /path/to/github-auto-login
pip install -e .
```

### Verify Installation

```bash
auth-cli status
```

## Quick Start

### 1. Start Daemon

```bash
auth-daemon daemon start

# Or run in background:
auth-daemon daemon start &
```

### 2. Authenticate with Service

```bash
# GitHub
gh auth login
# Daemon automatically detects device code, opens browser, enters code

# Google
gcloud auth login
# Daemon handles OAuth flow

# Anthropic
# Set auth in terminal, daemon will intercept
```

### 3. Check Cached Session

```bash
auth-cli get github
# Output: cached token, expiry, metadata
```

## CLI Reference

### Status

```bash
auth-cli status
# ✓ Auth daemon is running
```

### Start Auth Flow

```bash
auth-cli start github
auth-cli start google --browser Safari
auth-cli start slack --browser Chrome
```

### Get Cached Session

```bash
auth-cli get github
# Returns: token, refresh_token, expires_at, created_at
```

### Daemon Control

```bash
auth-daemon daemon start --port 8000
auth-daemon daemon status
auth-daemon daemon stop
```

## API Reference

### HTTP Endpoints

All requests go to `http://127.0.0.1:8000`

#### GET /health
Check daemon status.

```bash
curl http://127.0.0.1:8000/health
# {"status": "ok"}
```

#### POST /auth/start
Start an auth flow.

```bash
curl -X POST http://127.0.0.1:8000/auth/start \
  -H "Content-Type: application/json" \
  -d '{"service": "github"}'
```

#### POST /session/get
Get cached session for service.

```bash
curl -X POST http://127.0.0.1:8000/session/get \
  -H "Content-Type: application/json" \
  -d '{"service": "github"}'
# {"service": "github", "token": "...", "expires_at": ...}
```

## Configuration

### Service Configuration

Edit `~/.cache/auth-daemon/config.json` to customize auth flows:

```json
{
  "github": {
    "device_code_url": "https://github.com/login/device",
    "browser": "Chrome"
  },
  "google": {
    "device_code_url": "https://google.com/device",
    "browser": "Chrome"
  },
  "anthropic": {
    "token_endpoint": "https://api.anthropic.com/oauth/token",
    "browser": "Safari"
  }
}
```

### Terminal Watch Patterns

Define custom patterns in `~/.cache/auth-daemon/patterns.json`:

```json
{
  "my_service": {
    "device_code": "[A-Z0-9]{8,}",
    "url": "https://myservice.com/auth"
  }
}
```

## How It Works

### Device Flow (GitHub, Google)

1. User runs `gh auth login`
2. CLI outputs device code: `XXXX-XXXX`
3. Daemon watches terminal (via regex)
4. Detects code, opens browser to auth URL
5. Types code into browser
6. Clicks "Authorize" button
7. Captures success, caches token
8. CLI receives token via local API

### OAuth Redirect (Slack, Linear)

1. User starts auth flow
2. Daemon detects OAuth URL
3. Opens browser to consent URL
4. Clicks "Allow" button
5. Waits for redirect to localhost
6. Extracts token from callback
7. Caches session

## Accessibility / Automation Permissions

### macOS

On first use, macOS will prompt for Accessibility API access. Grant it to:

1. Terminal.app (or your IDE)
2. Python (when daemon runs)

To grant manually:
```bash
# System Preferences → Security & Privacy → Accessibility
# Add: Terminal.app, /usr/local/bin/python3, etc.
```

### Linux

No special permissions needed. `xdotool` works within user's X11/Wayland session.

### Windows

No special permissions needed. `pyautogui` works with Windows UI automation.

## Troubleshooting

### Daemon won't start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
pkill -f auth_daemon
```

### Accessibility API fails

```bash
# Grant access via System Preferences
# OR use Terminal with Full Disk Access:
# System Preferences → Security & Privacy → Full Disk Access → Terminal.app
```

### Code not detected

```bash
# Check daemon logs
tail -f ~/.cache/auth-daemon/daemon.log

# Verify pattern matches
python3 -c "import re; print(re.search('[A-Z0-9]{4}-[A-Z0-9]{4}', 'XXXX-XXXX'))"
```

### Browser not opening

```bash
# Check browser name (case-sensitive)
auth-cli start github --browser "Google Chrome"  # Not "Chrome"
```

## Advanced Usage

### Programmatic Access

```python
import requests

# Start auth flow
requests.post("http://127.0.0.1:8000/auth/start", 
              json={"service": "github"})

# Poll for token
import time
for i in range(60):
    resp = requests.post("http://127.0.0.1:8000/session/get",
                        json={"service": "github"})
    if resp.status_code == 200:
        token = resp.json()["token"]
        break
    time.sleep(1)
```

### Custom Service Handlers

Create custom handler in `auth_services.py`:

```python
class MyServiceAuthHandler(ServiceAuthHandler):
    def handle_device_code(self, code: str) -> bool:
        # Custom logic
        pass
    
    def extract_token(self, response) -> Optional[str]:
        # Custom token extraction
        pass

# Register in SERVICE_HANDLERS
SERVICE_HANDLERS["myservice"] = MyServiceAuthHandler
```

### Multi-User / Machine Setup

For shared machines, run daemon with user-specific cache:

```bash
export AUTH_CACHE_DIR=~/.cache/auth-daemon-$(whoami)
auth-daemon daemon start
```

## Security Notes

- **Session Storage**: Tokens cached in `~/.cache/auth-daemon/` (user-readable)
- **No Credential Storage**: Never stores passwords, only OAuth tokens
- **Local Only**: API only listens on 127.0.0.1 (no network exposure)
- **Browser Reuse**: Uses existing browser sessions (avoids rate limits)
- **Accessibility API**: Requires explicit user permission

## Platform Compatibility

| Feature | macOS | Linux | Windows |
|---------|-------|-------|---------|
| Device Code Detection | ✓ | ✓ | ✓ |
| Browser Automation | ✓ osascript | ✓ xdotool | ~ pyautogui |
| Button Clicking | ✓ | ✓ xdotool | ~ keyboard |
| Text Input | ✓ | ✓ xdotool | ✓ pyautogui |
| URL Opening | ✓ osascript | ✓ xdg-open | ✓ os.startfile |
| Session Caching | ✓ | ✓ | ✓ |
| HTTP API | ✓ | ✓ | ✓ |

## Limitations

- **Browser-dependent**: Requires browser with automation support
- **Visual element detection**: Relies on button text or accessibility labels
- **Single browser window**: Works best with one browser instance
- **Linux**: Requires X11/Wayland session (not headless)
- **Windows**: Limited without pyautogui (keyboard-only fallback)
- **Rate Limits**: GitHub rate-limits suspicious auth patterns

## Development

### Run daemon with debug logging

```bash
python3 auth_daemon.py
```

### Run tests

```bash
python3 -m pytest tests/
```

### Architecture Overview

- `auth_daemon.py`: Core daemon, HTTP server, terminal watcher, Accessibility API wrapper
- `auth_cli.py`: CLI client for daemon interaction
- `auth_services.py`: Service-specific auth handlers (GitHub, Google, etc.)
- `setup.py`: Installation configuration

## Contributing

Improvements welcome:

- Additional service handlers
- Better error recovery
- OCR fallback for visual elements
- Keyboard Maestro integration
- Extended logging/observability

## License

MIT
