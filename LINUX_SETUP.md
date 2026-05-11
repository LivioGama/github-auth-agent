# Linux Setup Guide

Complete setup instructions for auth daemon on Linux.

## Prerequisites

### System Packages

Install xdotool (required for UI automation):

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install xdotool python3-pip

# Fedora / RHEL
sudo dnf install xdotool python3-pip

# Arch / Manjaro
sudo pacman -S xdotool python3-pip

# openSUSE
sudo zypper install xdotool python3-pip
```

### Python 3.8+

Check your version:
```bash
python3 --version
```

If you need to upgrade:
```bash
sudo apt install python3.11  # Ubuntu/Debian
# or your distro's method
```

## Installation

### 1. Clone or download the project

```bash
cd ~/projects
git clone <repo-url> github-auto-login
cd github-auto-login
```

### 2. Install daemon

```bash
pip3 install --user -e .
# Or with sudo for system-wide:
sudo pip3 install -e .
```

Verify:
```bash
which auth-cli
auth-cli status
# ✗ Auth daemon is not running (expected)
```

### 3. Start daemon

```bash
# Foreground (for testing)
python3 auth_daemon.py

# Or background
auth-daemon daemon start &

# Or with nohup (survives terminal close)
nohup auth-daemon daemon start > ~/.cache/auth-daemon/daemon.log 2>&1 &
```

## Usage

### GitHub Authentication

```bash
# Terminal 1: Start daemon
auth-daemon daemon start

# Terminal 2: Run gh auth login
gh auth login

# Daemon will automatically:
# 1. Detect device code from terminal output
# 2. Open browser (Chrome, Firefox, Safari)
# 3. Type device code
# 4. Click Authorize button
# 5. Cache token
```

### Get Cached Token

```bash
auth-cli get github
# Output:
# {
#   "service": "github",
#   "token": "ghu_...",
#   "expires_at": 1234567890,
#   "created_at": 1234567890
# }
```

### Other Services

```bash
# Google
gcloud auth login
# Daemon handles automatically

# Anthropic / OpenAI
# Set auth in terminal, daemon intercepts

# Slack, Linear, Atlassian
auth-cli start slack
auth-cli start linear
auth-cli start atlassian
```

## X11 vs Wayland

The daemon works best with X11. Check your session type:

```bash
echo $XDG_SESSION_TYPE
# Should output: x11
# If output is: wayland, see below
```

### X11 (Recommended)

X11 is fully supported. xdotool works perfectly.

### Wayland (Partial Support)

Wayland support varies:
- ✓ Terminal watching works
- ✓ URL opening works
- ~ xdotool limited (may not find buttons)
- Workaround: Use X11 session, or allow manual clicks

To switch back to X11:

```bash
# At login screen: Click gear icon → "Ubuntu on Xorg" (or X11)
# Then log in

# Verify:
echo $XDG_SESSION_TYPE  # Should show: x11
```

## SSH / Remote Use

The daemon requires a graphical session (X11/Wayland).

### X11 Forwarding

```bash
# Local machine
ssh -X user@remote.host

# Then on remote
auth-daemon daemon start
auth-cli start github
# Browser opens on your local X11 display
```

### VNC / Remote Desktop

```bash
# On remote machine running VNC
vncserver :1 -geometry 1920x1080 -depth 24

# Connect from local
vncviewer remote.host:1

# Then in VNC session
auth-daemon daemon start
auth-cli start github
```

## Troubleshooting

### xdotool not found

```bash
# Install again
sudo apt install xdotool

# Verify
xdotool --version
```

### Daemon starts but doesn't click buttons

```bash
# Issue: xdotool can't find buttons, or Wayland session

# Check session type
echo $XDG_SESSION_TYPE

# If Wayland: Switch to X11 (see above)

# Check logs
tail -f ~/.cache/auth-daemon/daemon.log

# If "Failed to find button": May need manual click (acceptable)
```

### Browser not opening

```bash
# Check available browsers
which google-chrome chromium firefox

# Set browser in config
# Edit: ~/.cache/auth-daemon/config.json
# Change "browser": "Chrome" to "Chromium" or "Firefox"
```

### Terminal code not detected

```bash
# Check regex pattern
python3 -c "import re; print(re.match('[A-Z0-9]{4}-[A-Z0-9]{4}', 'XXXX-XXXX'))"

# Check daemon logs
tail -f ~/.cache/auth-daemon/daemon.log

# Try manual auth
auth-cli start github
```

### Port 8000 in use

```bash
# Find process using port
lsof -i :8000

# Kill it
kill <PID>

# Or use different port
auth-daemon daemon start --port 9000
```

## Performance

On Linux, the daemon is very fast:
- Startup: ~200ms
- Auth flow: ~15 seconds
- Token cache hit: ~30ms

## Systemd Integration (Optional)

Run daemon as systemd user service:

```bash
# Create user service
mkdir -p ~/.config/systemd/user

# Create service file
cat > ~/.config/systemd/user/auth-daemon.service << 'EOF'
[Unit]
Description=Auth Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/auth-daemon daemon start
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=default.target
EOF

# Enable and start
systemctl --user daemon-reload
systemctl --user enable auth-daemon.service
systemctl --user start auth-daemon.service

# Check status
systemctl --user status auth-daemon.service

# View logs
journalctl --user -u auth-daemon.service -f
```

## Docker / Container

To run in Docker:

```dockerfile
FROM ubuntu:22.04

RUN apt update && apt install -y \
    python3.10 \
    python3-pip \
    xdotool \
    xvfb \
    dbus

WORKDIR /opt/auth-daemon
COPY . .

RUN pip3 install -e .

# Run with virtual X server
CMD ["sh", "-c", "Xvfb :1 -screen 0 1920x1080x24 & export DISPLAY=:1 && auth-daemon daemon start"]
```

Build and run:
```bash
docker build -t auth-daemon .
docker run -it -p 8000:8000 auth-daemon
```

## Advanced Configuration

Edit `~/.cache/auth-daemon/config.json`:

```json
{
  "services": {
    "github": {
      "browser": "firefox"
    },
    "google": {
      "browser": "chromium"
    }
  }
}
```

Available browsers:
- `Chrome` / `Google Chrome`
- `Chromium`
- `Firefox`
- `Safari` (if available)
- Any command in PATH

## Uninstall

```bash
# Remove daemon
pip3 uninstall auth-daemon -y

# Remove cache
rm -rf ~/.cache/auth-daemon

# If using systemd
systemctl --user disable auth-daemon.service
```

## Next Steps

- [README.md](README.md) - Full documentation
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [examples.py](examples.py) - Code examples
- [tests.py](tests.py) - Run tests
