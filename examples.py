#!/usr/bin/env python3
"""
Examples of how to use auth daemon programmatically.
"""

import requests
import json
import time
from typing import Optional

DAEMON_URL = "http://127.0.0.1:8000"


def example_github_auth():
    """Example: Authenticate with GitHub and get token."""
    print("=== GitHub Auth Example ===\n")

    # Start auth flow
    print("Starting GitHub auth flow...")
    response = requests.post(
        f"{DAEMON_URL}/auth/start",
        json={"service": "github"},
    )
    print(f"Started: {response.json()}\n")

    # Poll for token (daemon will handle browser automation)
    print("Waiting for authentication...")
    token = None
    for attempt in range(60):  # Wait up to 60 seconds
        response = requests.post(
            f"{DAEMON_URL}/session/get",
            json={"service": "github"},
        )

        if response.status_code == 200:
            session = response.json()
            token = session.get("token")
            print(f"✓ Got token: {token[:20]}...")
            print(f"  Expires at: {session.get('expires_at')}\n")
            break

        print(f"  Attempt {attempt + 1}/60...")
        time.sleep(1)

    if not token:
        print("✗ Authentication timeout")

    return token


def example_multiple_services():
    """Example: Authenticate with multiple services."""
    print("=== Multi-Service Auth Example ===\n")

    services = ["github", "google", "slack"]
    tokens = {}

    for service in services:
        print(f"Starting {service} auth...")
        response = requests.post(
            f"{DAEMON_URL}/auth/start",
            json={"service": service},
        )

        if response.status_code == 200:
            # Poll for token
            for _ in range(60):
                token_response = requests.post(
                    f"{DAEMON_URL}/session/get",
                    json={"service": service},
                )

                if token_response.status_code == 200:
                    session = token_response.json()
                    tokens[service] = session.get("token")
                    print(f"✓ {service}: {session.get('token')[:20]}...\n")
                    break

                time.sleep(1)

    return tokens


def example_check_cached_session():
    """Example: Check if session is already cached."""
    print("=== Check Cached Session Example ===\n")

    service = "github"
    response = requests.post(
        f"{DAEMON_URL}/session/get",
        json={"service": service},
    )

    if response.status_code == 200:
        session = response.json()
        print(f"✓ Found cached {service} session:")
        print(f"  Token: {session.get('token')[:20]}...")
        print(f"  Created: {session.get('created_at')}")
        print(f"  Expires: {session.get('expires_at')}\n")
        return session.get("token")
    else:
        print(f"✗ No cached session for {service}")
        return None


def example_conditional_auth():
    """Example: Only auth if session is not cached."""
    print("=== Conditional Auth Example ===\n")

    service = "github"

    # Check if we have a cached session
    response = requests.post(
        f"{DAEMON_URL}/session/get",
        json={"service": service},
    )

    if response.status_code == 200:
        token = response.json().get("token")
        print(f"✓ Using cached token: {token[:20]}...")
        return token

    # No cached session, start auth flow
    print(f"No cached session, starting {service} auth...")
    response = requests.post(
        f"{DAEMON_URL}/auth/start",
        json={"service": service},
    )

    # Poll for token
    for _ in range(60):
        response = requests.post(
            f"{DAEMON_URL}/session/get",
            json={"service": service},
        )

        if response.status_code == 200:
            token = response.json().get("token")
            print(f"✓ Got new token: {token[:20]}...")
            return token

        time.sleep(1)

    print("✗ Authentication timeout")
    return None


def example_health_check():
    """Example: Check daemon health."""
    print("=== Health Check Example ===\n")

    try:
        response = requests.get(f"{DAEMON_URL}/health", timeout=2)
        if response.status_code == 200:
            print("✓ Daemon is running")
            print(f"  Status: {response.json()}\n")
            return True
    except requests.exceptions.RequestException as e:
        print(f"✗ Daemon is not running: {e}\n")

    return False


def example_with_context_manager():
    """Example: Using auth in a context manager pattern."""
    print("=== Context Manager Pattern Example ===\n")

    class AuthContext:
        def __init__(self, service: str):
            self.service = service
            self.token = None

        def __enter__(self):
            """Get token when entering context."""
            response = requests.post(
                f"{DAEMON_URL}/session/get",
                json={"service": self.service},
            )

            if response.status_code == 200:
                self.token = response.json().get("token")
                print(f"✓ Using token for {self.service}")
            else:
                print(f"✗ Failed to get token for {self.service}")

            return self.token

        def __exit__(self, exc_type, exc_val, exc_tb):
            """Cleanup."""
            pass

    # Usage
    with AuthContext("github") as token:
        if token:
            print(f"  Token: {token[:20]}...")
            # Use token for API calls
        else:
            print("  Failed to authenticate")


if __name__ == "__main__":
    # Check daemon is running
    if not example_health_check():
        print("Please start daemon: auth-daemon daemon start\n")
        exit(1)

    # Run examples
    # example_github_auth()
    # example_multiple_services()
    # example_check_cached_session()
    example_conditional_auth()
    # example_with_context_manager()

    print("Examples complete!")
