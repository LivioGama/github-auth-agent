# Quick Start Guide

Get up and running with auth daemon in 5 minutes.

## Platform Setup

### macOS
```bash
cd /path/to/github-auto-login
bash install.sh
# Then grant Accessibility API access in System Preferences
```

### Linux
```bash
# Install xdotool first
sudo apt install xdotool  # Ubuntu/Debian
# or
sudo dnf install xdotool  # Fedora
# or
sudo pacman -S xdotool    # Arch

# Install daemon
cd /path/to/github-auto-login
bash install.sh
```

### Windows
```bash
cd C:\path\to\github-auto-login
python -m pip install -e .
# Optional: pip install pyautogui (for better automation)
```

## Installation

```bash
cd /path/to/github-auto-login
bash install.sh
```

This will:
- Install Python dependencies (`requests`)
- Install CLI tools (`auth-cli`, `auth-daemon`)
- Create cache directory (`~/.cache/auth-daemon`)
- Copy configuration template

## Start Daemon

```bash
auth-daemon daemon start

# Or in background:
auth-daemon daemon start &

# Or verbose:
python3 auth_daemon.py
```

The daemon listens on `http://127.0.0.1:8000` and watches for auth codes.

## Authenticate with GitHub

In another terminal:

```bash
# Start auth
auth-cli start github

# Or manually:
gh auth login
# Daemon automatically:
# 1. Detects device code (XXXX-XXXX) from terminal
# 2. Opens browser to github.com/login/device
# 3. Types the code
# 4. Clicks "Authorize"
# 5. Caches token
```

## Check Status

```bash
# Is daemon running?
auth-cli status

# Get cached token
auth-cli get github
# Output: {
#   "service": "github",
#   "token": "ghu_...",
#   "expires_at": 1234567890,
#   "created_at": 1234567890
# }
```

## Use in Code

```python
import requests

# Get cached GitHub token
response = requests.post(
    "http://127.0.0.1:8000/session/get",
    json={"service": "github"}
)

if response.status_code == 200:
    token = response.json()["token"]
    # Use token for API calls
```

## Supported Services

- GitHub (`gh auth login`)
- Google (`gcloud auth login`)
- Anthropic
- OpenAI
- Slack
- Linear
- Atlassian

## Troubleshooting

### Daemon won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
pkill -f auth_daemon

# Start fresh
auth-daemon daemon start
```

### Code not detected
```bash
# Check logs
tail -f ~/.cache/auth-daemon/daemon.log

# Verify pattern matches
python3 -c "import re; print(re.match('[A-Z0-9]{4}-[A-Z0-9]{4}', 'XXXX-XXXX'))"
```

### macOS: Accessibility API not working
```bash
# Grant access to Terminal/IDE:
# System Preferences → Security & Privacy → Accessibility
# Add: Terminal.app (or your IDE)
```

### Linux: xdotool not found
```bash
# Install xdotool
sudo apt install xdotool      # Ubuntu/Debian
sudo dnf install xdotool      # Fedora
sudo pacman -S xdotool        # Arch

# Verify installation
xdotool --version
```

### Linux: Button click not working
```bash
# xdotool may need focus on browser window
# Try: Click browser window first, then run auth

# Or check if Wayland is in use (some xdotool features don't work on Wayland)
echo $XDG_SESSION_TYPE  # Should be "x11"
```

## Next Steps

1. Read [README.md](README.md) for full documentation
2. Explore [examples.py](examples.py) for programmatic usage
3. Run tests: `python3 tests.py`
4. Configure services: `~/.cache/auth-daemon/config.json`

## Commands Reference

```bash
# Daemon
auth-daemon daemon start          # Start daemon
auth-daemon daemon status         # Check status
auth-daemon daemon stop           # Stop daemon

# CLI
auth-cli status                   # Check daemon status
auth-cli start github             # Start GitHub auth
auth-cli start google --browser Safari
auth-cli get github               # Get cached token

# Local API
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/auth/start -d '{"service":"github"}'
curl -X POST http://127.0.0.1:8000/session/get -d '{"service":"github"}'
```

## Under the Hood

The daemon consists of:

1. **Terminal Watcher**: Monitors terminal output for device codes via regex
2. **Accessibility API**: Uses macOS Accessibility to interact with browser UI
3. **Service Handlers**: Custom logic for each service (GitHub, Google, etc)
4. **Session Manager**: Caches tokens persistently
5. **HTTP Server**: Local API on `localhost:8000`

```
Terminal Output
     ↓
Regex Detector (XXXX-XXXX)
     ↓
Browser Automation (Accessibility API)
     ↓
Click Authorize Button
     ↓
Token Extraction
     ↓
Session Cache
     ↓
CLI / HTTP API
```

## Security Notes

- Tokens stored in `~/.cache/auth-daemon/` (encrypted at rest recommended)
- No passwords stored, only OAuth tokens
- API only listens on `127.0.0.1` (no remote exposure)
- Requires macOS Accessibility API permission (explicit user grant)
- Browser reuse avoids rate limits and suspicious patterns

## Architecture

```python
# High-level flow
daemon = AuthDaemon()
daemon.terminal_watcher.register_callback("github", handle_github_code)
daemon.start_server(port=8000)  # HTTP API

# When terminal outputs "XXXX-XXXX":
# 1. Terminal watcher detects code
# 2. GitHub handler opens browser + types code
# 3. SessionManager caches token
# 4. CLI/API returns token to user
```

Enjoy automated auth! 🔐
