#!/bin/bash
# Install the GitHub Auth Agent (Python deps + CLI entry points + /Applications menu-bar app).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[install] checking Python..."
PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if ! "$PYTHON_BIN" -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "[install] error: Python 3.9+ required (found $PYTHON_VERSION)" >&2
    exit 1
fi
echo "[install] python $PYTHON_VERSION [OK]"

PYTHON_ABS="$(command -v "$PYTHON_BIN")"
echo "[install] python interpreter: $PYTHON_ABS"

echo "[install] installing package + dependencies..."
"$PYTHON_BIN" -m pip install -e "$REPO_ROOT"

echo "[install] installing GitHubAuthAgent.app into /Applications..."
APP_SRC="$REPO_ROOT/assets/GitHubAuthAgent.app"
APP_DEST="/Applications/GitHubAuthAgent.app"
LEGACY_DEST="/Applications/GitHubAuth.app"
if [[ -d "$APP_SRC" ]]; then
    rm -rf "$LEGACY_DEST"            # remove pre-rename install
    rm -rf "$APP_DEST"
    ditto "$APP_SRC" "$APP_DEST"

    # On macOS Tahoe, NSStatusBar items are only attached to the real menu bar
    # when the launching process's bundle identity is one of the system-trusted
    # bundles (e.g. org.python.python). A custom bundle id yields an
    # NSSceneStatusItem placed at (0,0) regardless of code signature. So the
    # launcher stays a Python shebang script: the running process is reported
    # as Python, but the status item works.
    LAUNCHER="$APP_DEST/Contents/MacOS/GitHubAuthAgent"
    sed -i '' "1s|.*|#!$PYTHON_ABS|" "$LAUNCHER"
    chmod +x "$LAUNCHER"

    codesign --force --deep --sign - "$APP_DEST" >/dev/null 2>&1 || true
    /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "$APP_DEST" || true
    echo "[install] GitHubAuthAgent.app -> $APP_DEST [OK]"
else
    echo "[install] warning: $APP_SRC not found, skipping app install" >&2
fi

cat <<EOF

[install] done.

Next steps:
  1. Grant Accessibility + Screen Recording permission to your python3
     under System Settings -> Privacy & Security.
  2. Capture a GitHub session for agent-browser (one time):
       agent-browser --state ~/.config/auth-daemon/github-auth.json \\
                     open https://github.com/login
     Log in manually in the window that pops up; close it.
  3. Open the menu-bar app (it also starts the daemon):
       open /Applications/GitHubAuthAgent.app
  4. Run \`gh auth login\`, leave the device code on screen,
     and press Cmd+G. The agent OCRs the screen and finishes the flow.
EOF
