#!/usr/bin/env python3
"""
Unit tests for auth daemon.
Run with: python3 -m pytest tests.py -v
Or directly: python3 tests.py
"""

import unittest
import time
import json
import re
from pathlib import Path
from auth_daemon import (
    AccessibilityAPI,
    TerminalWatcher,
    SessionManager,
    CachedSession,
    AUTH_PATTERNS,
)
from auth_services import (
    AuthFlowConfig,
    GitHubAuthHandler,
    get_handler,
)


class TestAccessibilityAPI(unittest.TestCase):
    """Test Accessibility API wrapper."""

    def test_get_active_app(self):
        """Test getting active application."""
        # This will work on macOS
        app = AccessibilityAPI.get_active_app()
        # Should return something (Terminal, Safari, etc) or None if not on macOS
        self.assertIsNotNone(app) or self.skipTest("Not on macOS")

    def test_open_url_syntax(self):
        """Test URL opening (don't actually open)."""
        # Just verify the method exists
        self.assertTrue(callable(AccessibilityAPI.open_url))

    def test_type_text_syntax(self):
        """Test text typing (don't actually type)."""
        self.assertTrue(callable(AccessibilityAPI.type_text))

    def test_click_button_syntax(self):
        """Test button clicking (don't actually click)."""
        self.assertTrue(callable(AccessibilityAPI.click_button))


class TestTerminalWatcher(unittest.TestCase):
    """Test terminal output watcher."""

    def test_github_device_code_pattern(self):
        """Test GitHub device code regex."""
        pattern = AUTH_PATTERNS["github"]["device_code"]
        regex = re.compile(pattern)

        # Valid codes
        self.assertIsNotNone(regex.search("XXXX-XXXX"))
        self.assertIsNotNone(regex.search("ABCD-1234"))
        self.assertIsNotNone(regex.search("First copy your one-time code: XXXX-XXXX"))

        # Invalid codes
        self.assertIsNone(regex.search("xxxx-xxxx"))  # lowercase
        self.assertIsNone(regex.search("XXX-XXX"))    # too short

    def test_watcher_callback(self):
        """Test watcher callback registration."""
        watcher = TerminalWatcher()
        callback_called = []

        def test_callback(code, url):
            callback_called.append((code, url))

        watcher.register_callback("github", test_callback)
        watcher._check_line("First copy your one-time code: ABCD-1234")

        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0][0], "ABCD-1234")

    def test_google_device_code_pattern(self):
        """Test Google device code regex."""
        pattern = AUTH_PATTERNS["google"]["device_code"]
        regex = re.compile(pattern)

        # Valid codes
        self.assertIsNotNone(regex.search("ABC123DEF456"))
        self.assertIsNotNone(regex.search("VERYLONGCODE"))

        # Invalid
        self.assertIsNone(regex.search("SHORT"))


class TestSessionManager(unittest.TestCase):
    """Test session caching."""

    def setUp(self):
        """Create temporary cache directory."""
        self.cache_dir = Path("/tmp/test_auth_cache")
        self.cache_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test cache."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)

    def test_store_session(self):
        """Test storing a session."""
        manager = SessionManager(self.cache_dir)
        manager.store("test_service", "test_token")

        session = manager.get("test_service")
        self.assertIsNotNone(session)
        self.assertEqual(session.token, "test_token")
        self.assertEqual(session.service, "test_service")

    def test_session_expiry(self):
        """Test session expiry checking."""
        manager = SessionManager(self.cache_dir)

        # Store session with 1 second expiry
        manager.store("test_service", "test_token", expires_in=1)
        session = manager.get("test_service")
        self.assertIsNotNone(session)

        # Wait for expiry
        time.sleep(1.1)
        expired_session = manager.get("test_service")
        self.assertIsNone(expired_session)

    def test_session_persistence(self):
        """Test session persistence across instances."""
        # Create and store
        manager1 = SessionManager(self.cache_dir)
        manager1.store("test_service", "persistent_token")

        # Load in new instance
        manager2 = SessionManager(self.cache_dir)
        session = manager2.get("test_service")
        self.assertIsNotNone(session)
        self.assertEqual(session.token, "persistent_token")

    def test_clear_session(self):
        """Test clearing a session."""
        manager = SessionManager(self.cache_dir)
        manager.store("test_service", "test_token")

        session = manager.get("test_service")
        self.assertIsNotNone(session)

        manager.clear("test_service")
        cleared_session = manager.get("test_service")
        self.assertIsNone(cleared_session)


class TestServiceHandlers(unittest.TestCase):
    """Test service-specific handlers."""

    def setUp(self):
        """Set up test fixtures."""
        self.cache_dir = Path("/tmp/test_auth_handlers")
        self.cache_dir.mkdir(exist_ok=True)
        self.session_manager = SessionManager(self.cache_dir)
        self.api = AccessibilityAPI()

    def tearDown(self):
        """Clean up."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)

    def test_github_handler_creation(self):
        """Test creating GitHub handler."""
        config = AuthFlowConfig(
            service_name="github",
            device_code_url="https://github.com/login/device",
        )

        handler = get_handler("github", config, self.api, self.session_manager)
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, GitHubAuthHandler)

    def test_extract_token(self):
        """Test token extraction."""
        config = AuthFlowConfig(
            service_name="github",
            device_code_url="https://github.com/login/device",
        )

        handler = get_handler("github", config, self.api, self.session_manager)
        response = {"access_token": "test_token_12345"}
        token = handler.extract_token(response)

        self.assertEqual(token, "test_token_12345")

    def test_all_handlers_registered(self):
        """Test that all service handlers are registered."""
        services = ["github", "google", "anthropic", "openai", "slack", "linear", "atlassian"]
        config = AuthFlowConfig(
            service_name="test",
            device_code_url="https://test.com",
        )

        for service in services:
            handler = get_handler(service, config, self.api, self.session_manager)
            self.assertIsNotNone(handler, f"Handler for {service} not found")


class TestAuthPatterns(unittest.TestCase):
    """Test auth code patterns."""

    def test_all_patterns_defined(self):
        """Test that patterns exist for all services."""
        services = ["github", "google"]

        for service in services:
            self.assertIn(service, AUTH_PATTERNS)
            self.assertIn("device_code", AUTH_PATTERNS[service])
            self.assertIn("url", AUTH_PATTERNS[service])

    def test_pattern_validity(self):
        """Test that patterns are valid regex."""
        for service, pattern_info in AUTH_PATTERNS.items():
            if "device_code" in pattern_info:
                pattern = pattern_info["device_code"]
                try:
                    re.compile(pattern)
                except re.error:
                    self.fail(f"Invalid regex for {service}: {pattern}")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestAccessibilityAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestTerminalWatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestSessionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestServiceHandlers))
    suite.addTests(loader.loadTestsFromTestCase(TestAuthPatterns))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import sys
    sys.exit(run_tests())
