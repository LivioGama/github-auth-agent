#!/bin/bash
# Installation script for auth daemon

set -e

DAEMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN=${PYTHON_BIN:-python3}

echo "🔐 Auth Daemon Installer"
echo "========================="
echo ""

# Check Python version
echo "Checking Python..."
PYTHON_VERSION=$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" < "3.8" ]]; then
    echo "✗ Python 3.8+ required"
    exit 1
fi

echo ""

# Install dependencies
echo "Installing dependencies..."
$PYTHON_BIN -m pip install -r "$DAEMON_DIR/requirements.txt" >/dev/null 2>&1
echo "✓ Dependencies installed"

echo ""

# Install CLI
echo "Installing CLI..."
$PYTHON_BIN -m pip install -e "$DAEMON_DIR" >/dev/null 2>&1
echo "✓ CLI installed"

echo ""

# Create cache directory
echo "Setting up cache directory..."
CACHE_DIR="$HOME/.cache/auth-daemon"
mkdir -p "$CACHE_DIR"
mkdir -p "$CACHE_DIR/logs"
echo "✓ Cache directory: $CACHE_DIR"

echo ""

# Copy config template
echo "Setting up configuration..."
if [[ ! -f "$CACHE_DIR/config.json" ]]; then
    cp "$DAEMON_DIR/config.example.json" "$CACHE_DIR/config.json"
    echo "✓ Config created: $CACHE_DIR/config.json"
else
    echo "ℹ Config already exists (not overwriting)"
fi

echo ""

# Grant Accessibility permissions (interactive)
echo "Accessibility API Setup"
echo "======================="
echo ""
echo "The daemon needs Accessibility API access to automate browser UI."
echo ""
echo "To grant access:"
echo "1. Open: System Preferences → Security & Privacy → Accessibility"
echo "2. Click the lock to unlock"
echo "3. Add Terminal.app and/or your IDE"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Skipped. You can grant access later in System Preferences."
fi

echo ""

# Test installation
echo "Testing installation..."
if auth-cli status >/dev/null 2>&1; then
    echo "✓ Daemon is already running"
elif command -v auth-cli &> /dev/null; then
    echo "✓ CLI installed successfully"
    echo ""
    echo "Start daemon with: auth-daemon daemon start"
else
    echo "✗ CLI not found in PATH"
    echo "Try: export PATH=$HOME/.local/bin:\$PATH"
fi

echo ""
echo "✓ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Start daemon:      auth-daemon daemon start"
echo "2. Check status:      auth-cli status"
echo "3. Try example:       python3 examples.py"
echo ""
echo "Documentation: README.md"
