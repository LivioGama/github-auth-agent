"""
Service-specific auth handlers for OAuth flows.
Supports: GitHub, Google, Anthropic, OpenAI, Slack, Linear, Atlassian
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
import time

from auth_daemon import AccessibilityAPI, SessionManager


@dataclass
class AuthFlowConfig:
    """Configuration for an OAuth flow."""
    service_name: str
    device_code_url: str
    token_endpoint: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: list = None
    browser: str = "Chrome"


class ServiceAuthHandler(ABC):
    """Base class for service-specific auth handlers."""

    def __init__(
        self,
        config: AuthFlowConfig,
        accessibility_api: AccessibilityAPI,
        session_manager: SessionManager,
    ):
        self.config = config
        self.api = accessibility_api
        self.session_manager = session_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def handle_device_code(self, code: str) -> bool:
        """Handle device code flow. Return True on success."""
        pass

    @abstractmethod
    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract token from API response."""
        pass

    def cache_session(
        self,
        token: str,
        refresh_token: Optional[str] = None,
        expires_in: int = 3600,
    ) -> None:
        """Cache authenticated session."""
        self.session_manager.store(
            self.config.service_name,
            token,
            refresh_token,
            expires_in,
        )


class GitHubAuthHandler(ServiceAuthHandler):
    """GitHub device flow auth handler."""

    def handle_device_code(self, code: str) -> bool:
        """Open GitHub auth URL and enter device code."""
        self.logger.info(f"Starting GitHub auth with code: {code}")

        # Open auth URL
        if not self.api.open_url(self.config.device_code_url, self.config.browser):
            self.logger.error("Failed to open browser")
            return False

        time.sleep(2)

        # Type device code (split into two parts with hyphen)
        code_parts = code.split("-")
        for i, part in enumerate(code_parts):
            if not self.api.type_text(part):
                self.logger.error(f"Failed to type code part {i}")
                return False
            if i < len(code_parts) - 1:
                # Type hyphen
                self.api.type_text("-")
            time.sleep(0.3)

        time.sleep(0.5)

        # Press Enter to confirm
        self.api.type_text("\r")
        time.sleep(1)

        # Click Authorize button
        if not self.api.click_button("Authorize"):
            self.logger.warning("Failed to click Authorize button (may require manual click)")

        self.logger.info("GitHub auth flow completed")
        return True

    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract GitHub token from response."""
        return response.get("access_token")


class GoogleAuthHandler(ServiceAuthHandler):
    """Google device flow auth handler."""

    def handle_device_code(self, code: str) -> bool:
        """Open Google auth URL and enter device code."""
        self.logger.info(f"Starting Google auth with code: {code}")

        if not self.api.open_url(self.config.device_code_url, self.config.browser):
            self.logger.error("Failed to open browser")
            return False

        time.sleep(2)

        # Type device code
        if not self.api.type_text(code):
            self.logger.error("Failed to type device code")
            return False

        time.sleep(0.5)

        # Press Enter
        self.api.type_text("\r")
        time.sleep(1)

        # Click Next/Continue button
        if not self.api.click_button("Next"):
            if not self.api.click_button("Continue"):
                self.logger.warning("Failed to click Next/Continue")

        self.logger.info("Google auth flow completed")
        return True

    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract Google token from response."""
        return response.get("access_token")


class AnthropicAuthHandler(ServiceAuthHandler):
    """Anthropic API key / OAuth handler."""

    def handle_device_code(self, code: str) -> bool:
        """Handle Anthropic auth (typically API key or OAuth)."""
        self.logger.info("Starting Anthropic auth")

        if not self.api.open_url(self.config.device_code_url, self.config.browser):
            self.logger.error("Failed to open browser")
            return False

        time.sleep(2)

        # Type code/key
        if not self.api.type_text(code):
            self.logger.error("Failed to enter code")
            return False

        time.sleep(0.5)
        self.api.type_text("\r")

        self.logger.info("Anthropic auth completed")
        return True

    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract Anthropic token from response."""
        return response.get("api_key") or response.get("access_token")


class OpenAIAuthHandler(ServiceAuthHandler):
    """OpenAI API key / OAuth handler."""

    def handle_device_code(self, code: str) -> bool:
        """Handle OpenAI auth."""
        self.logger.info("Starting OpenAI auth")

        if not self.api.open_url(self.config.device_code_url, self.config.browser):
            self.logger.error("Failed to open browser")
            return False

        time.sleep(2)

        if not self.api.type_text(code):
            self.logger.error("Failed to enter API key")
            return False

        time.sleep(0.5)
        self.api.type_text("\r")

        self.logger.info("OpenAI auth completed")
        return True

    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract OpenAI token from response."""
        return response.get("api_key") or response.get("access_token")


class SlackAuthHandler(ServiceAuthHandler):
    """Slack OAuth handler."""

    def handle_device_code(self, code: str) -> bool:
        """Handle Slack OAuth flow."""
        self.logger.info("Starting Slack auth")

        if not self.api.open_url(self.config.device_code_url, self.config.browser):
            self.logger.error("Failed to open browser")
            return False

        time.sleep(2)

        # Slack typically shows permission prompt
        # Click "Allow" or "Authorize" button
        if not self.api.click_button("Allow"):
            if not self.api.click_button("Authorize"):
                self.logger.warning("Failed to click authorization button")

        self.logger.info("Slack auth completed")
        return True

    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract Slack token from response."""
        return response.get("access_token") or response.get("token")


class LinearAuthHandler(ServiceAuthHandler):
    """Linear OAuth handler."""

    def handle_device_code(self, code: str) -> bool:
        """Handle Linear OAuth flow."""
        self.logger.info("Starting Linear auth")

        if not self.api.open_url(self.config.device_code_url, self.config.browser):
            self.logger.error("Failed to open browser")
            return False

        time.sleep(2)

        # Linear shows OAuth consent
        if not self.api.click_button("Authorize"):
            self.logger.warning("Failed to click Authorize")

        self.logger.info("Linear auth completed")
        return True

    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract Linear token from response."""
        return response.get("access_token")


class AtlassianAuthHandler(ServiceAuthHandler):
    """Atlassian (Jira, Confluence) OAuth handler."""

    def handle_device_code(self, code: str) -> bool:
        """Handle Atlassian OAuth flow."""
        self.logger.info("Starting Atlassian auth")

        if not self.api.open_url(self.config.device_code_url, self.config.browser):
            self.logger.error("Failed to open browser")
            return False

        time.sleep(2)

        # Atlassian OAuth consent
        if not self.api.click_button("Allow"):
            if not self.api.click_button("Authorize"):
                self.logger.warning("Failed to click authorization button")

        self.logger.info("Atlassian auth completed")
        return True

    def extract_token(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract Atlassian token from response."""
        return response.get("access_token")


# Service registry
SERVICE_HANDLERS = {
    "github": GitHubAuthHandler,
    "google": GoogleAuthHandler,
    "anthropic": AnthropicAuthHandler,
    "openai": OpenAIAuthHandler,
    "slack": SlackAuthHandler,
    "linear": LinearAuthHandler,
    "atlassian": AtlassianAuthHandler,
    "jira": AtlassianAuthHandler,  # Alias
}


def get_handler(
    service: str,
    config: AuthFlowConfig,
    accessibility_api: AccessibilityAPI,
    session_manager: SessionManager,
) -> Optional[ServiceAuthHandler]:
    """Get service handler by name."""
    handler_class = SERVICE_HANDLERS.get(service.lower())
    if not handler_class:
        logging.error(f"Unknown service: {service}")
        return None

    return handler_class(config, accessibility_api, session_manager)
