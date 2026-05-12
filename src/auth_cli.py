#!/usr/bin/env python3
"""CLI client for the auth daemon.

Usage:
  auth-cli status                          - check daemon health
  auth-cli start github --code XXXX-XXXX   - trigger an auth flow
  auth-cli daemon start [--port 8000]      - run the daemon (blocking)
  auth-cli daemon stop                     - stop a running daemon
"""

import argparse
import os
import subprocess
import sys

import requests

DAEMON_URL = os.environ.get("AUTH_DAEMON_URL", "http://127.0.0.1:8000")


def _check_daemon() -> bool:
    try:
        return requests.get(f"{DAEMON_URL}/health", timeout=2).status_code == 200
    except requests.exceptions.RequestException:
        return False


def cmd_status() -> int:
    if _check_daemon():
        print("[OK] auth daemon is running")
        return 0
    print("[FAIL] auth daemon is not running", file=sys.stderr)
    return 1


def cmd_start(service: str, code: str | None) -> int:
    if not _check_daemon():
        print("[FAIL] auth daemon is not running. Start it with: auth-cli daemon start",
              file=sys.stderr)
        return 1
    payload = {"service": service}
    if code:
        payload["device_code"] = code
    try:
        r = requests.post(f"{DAEMON_URL}/auth/start", json=payload, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] request error: {e}", file=sys.stderr)
        return 1
    if r.status_code != 200:
        print(f"[FAIL] {r.status_code}: {r.text}", file=sys.stderr)
        return 1
    print(f"[OK] {service} auth started")
    return 0


def cmd_daemon_start(port: int) -> int:
    from auth_daemon import AuthDaemon
    try:
        AuthDaemon().start_server(port=port)
    except KeyboardInterrupt:
        print("\n[OK] daemon stopped")
    return 0


def cmd_daemon_stop() -> int:
    r = subprocess.run(["pkill", "-f", "auth_daemon.py"])
    if r.returncode == 0:
        print("[OK] daemon stopped")
        return 0
    print("[FAIL] no running daemon found", file=sys.stderr)
    return 1


def main() -> int:
    p = argparse.ArgumentParser(prog="auth-cli", description="Auth daemon CLI client")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="check daemon status")

    start_p = sub.add_parser("start", help="trigger an auth flow")
    start_p.add_argument("service", help="service name (only 'github' is supported)")
    start_p.add_argument("--code", help="device code (XXXX-XXXX)")

    daemon_p = sub.add_parser("daemon", help="daemon process management")
    daemon_p.add_argument("action", choices=["start", "stop", "status"])
    daemon_p.add_argument("--port", type=int, default=8000)

    args = p.parse_args()

    if args.command == "status":
        return cmd_status()
    if args.command == "start":
        return cmd_start(args.service, args.code)
    if args.command == "daemon":
        if args.action == "start":
            return cmd_daemon_start(args.port)
        if args.action == "stop":
            return cmd_daemon_stop()
        return cmd_status()
    return 1


if __name__ == "__main__":
    sys.exit(main())
