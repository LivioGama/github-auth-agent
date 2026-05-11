#!/usr/bin/env python3
"""
CLI client for auth daemon.
Usage: auth-cli <command> [options]
"""

import sys
import json
import argparse
import requests
from typing import Optional
from pathlib import Path

DAEMON_URL = "http://127.0.0.1:8000"

def check_daemon() -> bool:
    """Check if daemon is running."""
    try:
        response = requests.get(f"{DAEMON_URL}/health", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def start_auth(service: str) -> dict:
    """Start auth flow for a service."""
    try:
        response = requests.post(
            f"{DAEMON_URL}/auth/start",
            json={"service": service},
            timeout=30,
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_session(service: str) -> Optional[dict]:
    """Get cached session for service."""
    try:
        response = requests.post(
            f"{DAEMON_URL}/session/get",
            json={"service": service},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Auth daemon CLI client",
        prog="auth-cli",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status command
    subparsers.add_parser("status", help="Check daemon status")

    # start command
    start_parser = subparsers.add_parser("start", help="Start auth flow")
    start_parser.add_argument("service", help="Service name (github, google, etc)")
    start_parser.add_argument(
        "--browser",
        default="Chrome",
        help="Browser to use (Chrome, Safari, Firefox)",
    )

    # get command
    get_parser = subparsers.add_parser("get", help="Get cached session")
    get_parser.add_argument("service", help="Service name")

    # daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Daemon operations")
    daemon_parser.add_argument(
        "action",
        choices=["start", "stop", "status"],
        help="Daemon action",
    )
    daemon_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")

    args = parser.parse_args()

    if args.command == "status":
        if check_daemon():
            print("✓ Auth daemon is running")
            sys.exit(0)
        else:
            print("✗ Auth daemon is not running")
            sys.exit(1)

    elif args.command == "start":
        if not check_daemon():
            print("Error: Auth daemon is not running. Start it with: auth-cli daemon start")
            sys.exit(1)

        result = start_auth(args.service)
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        print(f"Starting {args.service} auth flow...")
        print(json.dumps(result, indent=2))

    elif args.command == "get":
        session = get_session(args.service)
        if session:
            print(json.dumps(session, indent=2))
        else:
            print(f"No valid session for {args.service}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "daemon":
        if args.action == "start":
            from auth_daemon import AuthDaemon
            daemon = AuthDaemon()
            try:
                daemon.start_server(port=args.port)
            except KeyboardInterrupt:
                print("\nDaemon stopped")
        elif args.action == "status":
            if check_daemon():
                print("✓ Auth daemon is running")
            else:
                print("✗ Auth daemon is not running")
        elif args.action == "stop":
            print("Use: killall python3 (to stop daemon)")

    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
