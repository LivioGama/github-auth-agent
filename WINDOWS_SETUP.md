# Windows Setup Guide

Complete setup instructions for auth daemon on Windows.

## Prerequisites

### Python 3.8+

Download from [python.org](https://www.python.org/downloads/) or use package manager:

```powershell
# Using Chocolatey
choco install python

# Using Windows Package Manager
winget install Python.Python.3.11
```

Verify:
```powershell
python --version
```

### Optional: pyautogui

For better UI automation (recommended):

```powershell
pip install pyautogui
```

Without pyautogui, the daemon uses keyboard-only fallback (less reliable).

## Installation

### 1. Clone or download project

```powershell
cd ~\projects
git clone <repo-url> github-auto-login
cd github-auto-login
```

Or download ZIP and extract.

### 2. Install daemon

```powershell
pip install -e .
# Or if pip not in PATH:
python -m pip install -e .
```

Verify:
```powershell
auth-cli status
# ✗ Auth daemon is not running (expected)
```

If `auth-cli` not found, add Python scripts to PATH:

```powershell
# Find Python Scripts directory
python -c "import site; print(site.USER_SITE)"

# Add to PATH (temporary, for this session)
$env:PATH += ";C:\Users\YourName\AppData\Roaming\Python\Python311\Scripts"

# Add to PATH permanently (Run as Administrator)
# Control Panel → System → Advanced → Environment Variables
# Add: C:\Users\YourName\AppData\Roaming\Python\Python311\Scripts
```

### 3. Start daemon

```powershell
# Foreground (for testing)
python auth_daemon.py

# Or background
Start-Process powershell -ArgumentList "auth-daemon daemon start" -NoNewWindow

# Or with Task Scheduler (survives logout)
# See "Systemd Integration" section below
```

## Usage

### GitHub Authentication

```powershell
# Terminal 1: Start daemon
auth-daemon daemon start

# Terminal 2: Run gh auth login
gh auth login

# Daemon will automatically:
# 1. Detect device code from terminal output
# 2. Open browser (Chrome, Firefox, Edge)
# 3. Type device code
# 4. Click Authorize button (or keyboard fallback)
# 5. Cache token
```

### Get Cached Token

```powershell
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

```powershell
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

## Troubleshooting

### auth-cli command not found

```powershell
# Install in user directory
python -m pip install --user -e .

# Add Scripts to PATH (see Installation step 2)

# Or run directly
python auth_cli.py status
python auth_cli.py start github
```

### Daemon starts but doesn't automate buttons

Windows UI automation is less reliable than macOS/Linux.

```powershell
# Install pyautogui for better support
pip install pyautogui

# Check logs
Get-Content $env:USERPROFILE\.cache\auth-daemon\daemon.log -Tail 20

# Current limitation: Uses keyboard fallback
# Workaround: Allow manual button clicks (still faster than full manual auth)
```

### Browser not opening

```powershell
# Check available browsers
gcm chrome, firefox, msedge

# Set browser in config
# Edit: $env:USERPROFILE\.cache\auth-daemon\config.json
# Change "browser": "Chrome" to "Firefox" or "msedge"
```

### Port 8000 in use

```powershell
# Find process using port
netstat -ano | findstr :8000

# Kill process
taskkill /PID <PID> /F

# Or use different port
auth-daemon daemon start --port 9000
```

### Terminal code not detected

```powershell
# Check regex pattern
python -c "import re; print(re.match('[A-Z0-9]{4}-[A-Z0-9]{4}', 'XXXX-XXXX'))"

# Check daemon logs
Get-Content $env:USERPROFILE\.cache\auth-daemon\daemon.log -Tail 50 -Wait

# Try manual auth
auth-cli start github
```

## Task Scheduler Integration (Optional)

Run daemon at startup via Task Scheduler:

### 1. Create scheduled task

```powershell
# Run as Administrator
$Action = New-ScheduledTaskAction -Execute "python" -Argument "auth_daemon.py" -WorkingDirectory "$env:USERPROFILE\projects\github-auto-login"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive
$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Principal $Principal -Description "Auth Daemon"
Register-ScheduledTask -TaskName "AuthDaemon" -InputObject $Task
```

### 2. Start the task

```powershell
Start-ScheduledTask -TaskName "AuthDaemon"
```

### 3. View logs

```powershell
Get-ScheduledTaskInfo -TaskName "AuthDaemon"
```

### 4. Remove (if needed)

```powershell
Unregister-ScheduledTask -TaskName "AuthDaemon" -Confirm:$false
```

## Docker / WSL

### Windows Subsystem for Linux (WSL2)

If you have WSL2 installed:

```powershell
# Install WSL if needed
wsl --install -d Ubuntu

# Then follow Linux setup guide
# See LINUX_SETUP.md
```

### Docker Desktop

```dockerfile
FROM mcr.microsoft.com/windows/servercore:ltsc2022

RUN powershell -Command \
    iwr https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe -OutFile python.exe ; \
    .\python.exe /quiet InstallAllUsers=1 PrependPath=1

WORKDIR C:\auth-daemon
COPY . .

RUN pip install -e .

CMD ["python", "auth_daemon.py"]
```

Build:
```powershell
docker build -t auth-daemon .
docker run -p 8000:8000 auth-daemon
```

## Performance

On Windows, the daemon is reasonably fast:
- Startup: ~500ms
- Auth flow: ~20-30 seconds (includes user action)
- Token cache hit: ~50ms
- HTTP request: ~10ms

## Known Limitations

### UI Automation

Windows UI automation without pyautogui is limited:
- Can open URLs: ✓
- Can type text: ~ (uses SendKeys, may be slow)
- Can click buttons: ✗ (keyboard fallback only)

**Workaround**: Install pyautogui for better automation.

### Headless Browsers

Windows doesn't work well with headless browsers (no UI to automate).

**Supported browsers**:
- Chrome
- Edge
- Firefox
- Opera

### Virtual Machines

Some VMs (Hyper-V, VirtualBox) may have issues with UI automation.

**Workaround**: Use WSL2 with X11 forwarding, or Docker.

## Advanced Configuration

Edit `%USERPROFILE%\.cache\auth-daemon\config.json`:

```json
{
  "services": {
    "github": {
      "browser": "firefox"
    },
    "google": {
      "browser": "chrome"
    }
  }
}
```

Available browsers:
- `Chrome` / `Google Chrome`
- `Edge` / `msedge`
- `Firefox`
- Any command in PATH

## Uninstall

```powershell
# Remove daemon
pip uninstall auth-daemon -y

# Remove cached tokens
Remove-Item -Recurse -Force $env:USERPROFILE\.cache\auth-daemon

# Remove Task Scheduler job (if created)
Unregister-ScheduledTask -TaskName "AuthDaemon" -Confirm:$false
```

## Next Steps

- [README.md](README.md) - Full documentation
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [examples.py](examples.py) - Code examples
- [tests.py](tests.py) - Run tests

## Alternative: GitHub CLI with Browser

If automation is too difficult, you can use GitHub CLI with browser:

```powershell
# Use GitHub CLI with web browser (no daemon needed)
gh auth login --web

# But daemon automates this, which is why it's useful
```
