.PHONY: help install daemon status stop clean app

PYTHON := python3

help:
	@echo "GitHub Auth Agent - macOS GitHub device-flow automation"
	@echo ""
	@echo "Targets:"
	@echo "  make install   - Install dependencies, CLI, shell hook, and /Applications app"
	@echo "  make daemon    - Run the daemon (foreground)"
	@echo "  make app       - Open /Applications/GitHubAuthAgent.app (menu-bar UI)"
	@echo "  make status    - Check daemon status"
	@echo "  make stop      - Stop a running daemon"
	@echo "  make clean     - Remove caches and build artifacts"

install:
	@bash scripts/install.sh

daemon:
	@$(PYTHON) src/auth_daemon.py

app:
	@open /Applications/GitHubAuthAgent.app

status:
	@$(PYTHON) src/auth_cli.py status

stop:
	@$(PYTHON) src/auth_cli.py daemon stop

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete
	@rm -rf build dist *.egg-info
	@echo "[clean] removed caches and build artifacts (credentials & logs left intact)"
