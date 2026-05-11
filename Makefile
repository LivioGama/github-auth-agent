.PHONY: install test run daemon client status clean help

PYTHON := python3

help:
	@echo "Auth Daemon Makefile"
	@echo "==================="
	@echo ""
	@echo "Targets:"
	@echo "  make install    - Install daemon and CLI"
	@echo "  make daemon     - Start auth daemon"
	@echo "  make client     - Show CLI commands"
	@echo "  make status     - Check daemon status"
	@echo "  make test       - Run tests"
	@echo "  make examples   - Run examples"
	@echo "  make clean      - Clean cache and temp files"
	@echo ""

install:
	@bash install.sh

daemon:
	@$(PYTHON) auth_daemon.py

client:
	@$(PYTHON) auth_cli.py --help

status:
	@$(PYTHON) auth_cli.py status

test:
	@$(PYTHON) -m pytest tests.py -v || $(PYTHON) tests.py

examples:
	@$(PYTHON) examples.py

clean:
	@echo "Cleaning..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@rm -rf build dist *.egg-info
	@rm -f ~/.cache/auth-daemon/sessions.pkl
	@echo "Done"

.PHONY: install-dev
install-dev: install
	@$(PYTHON) -m pip install pytest black flake8 -q
	@echo "✓ Dev dependencies installed"

.PHONY: format
format:
	@$(PYTHON) -m black *.py --quiet
	@echo "✓ Code formatted"

.PHONY: lint
lint:
	@$(PYTHON) -m flake8 *.py --max-line-length=100
	@echo "✓ Lint complete"
