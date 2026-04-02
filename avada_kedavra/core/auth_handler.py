# -*- coding: utf-8 -*-
"""Authentication handling and re-authentication logic."""

import time
import threading
from typing import Optional, Dict, Any, Tuple

import requests

from ..models.auth import AuthConfig, AuthType, AuthState, TokenLocation, InjectAs
from ..utils.exceptions import AuthenticationError


class AuthHandler:
    """Manages authentication state and re-authentication for scans.

    Thread-safe: uses a lock so that only one worker thread performs
    re-authentication at a time while others wait.
    """

    def __init__(self, config: AuthConfig):
        """Initialize the auth handler.

        Args:
            config: Authentication configuration.
        """
        self.config = config
        self.state = AuthState()
        self._lock = threading.Lock()
        self._reauth_in_progress = threading.Event()
        self._reauth_in_progress.set()  # Start in "not re-authing" state

    def perform_login(
        self,
        session: requests.Session,
        proxies: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
        timeout: int = 10
    ) -> bool:
        """Perform authentication against the configured login endpoint.

        For API key auth, this just marks the static key as "authenticated".

        Args:
            session: Requests session for connection pooling.
            proxies: Optional proxy config.
            verify_ssl: Whether to verify SSL certificates.
            timeout: Request timeout in seconds.

        Returns:
            True if login succeeded.

        Raises:
            AuthenticationError: If login fails after configuration is valid.
        """
        if self.config.auth_type == AuthType.API_KEY:
            self.state.current_token = self.config.api_key
            self.state.is_authenticated = True
            self.state.successful_auths += 1
            return True

        if not self.config.login_url:
            raise AuthenticationError("No login URL configured")

        self.state.auth_attempts += 1

        try:
            request_args: Dict[str, Any] = {
                'method': self.config.login_method,
                'url': self.config.login_url,
                'verify': verify_ssl,
                'timeout': timeout,
                'proxies': proxies,
            }

            if self.config.credentials_format == 'json':
                request_args['json'] = self.config.credentials
            else:
                request_args['data'] = self.config.credentials

            response = session.request(**request_args)

            if response.status_code >= 400:
                self.state.failed_auths += 1
                raise AuthenticationError(
                    f"Login failed with status {response.status_code}: "
                    f"{response.text[:200]}"
                )

            token = self._extract_token(response)
            if not token:
                self.state.failed_auths += 1
                raise AuthenticationError(
                    f"Could not extract token from login response "
                    f"(field: '{self.config.token_field}', "
                    f"location: '{self.config.token_location.value}')"
                )

            self.state.current_token = token
            self.state.is_authenticated = True
            self.state.successful_auths += 1
            return True

        except AuthenticationError:
            raise
        except requests.exceptions.RequestException as e:
            self.state.failed_auths += 1
            raise AuthenticationError(f"Login request failed: {e}")

    def _extract_token(self, response: requests.Response) -> Optional[str]:
        """Extract authentication token from login response.

        Args:
            response: The login response.

        Returns:
            Extracted token string, or None if extraction failed.
        """
        if self.config.token_location == TokenLocation.BODY:
            try:
                body = response.json()
                # Support nested field access with dot notation (e.g., "data.token")
                value = body
                for key in self.config.token_field.split('.'):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        return None
                return str(value) if value is not None else None
            except (ValueError, AttributeError):
                return None

        elif self.config.token_location == TokenLocation.HEADER:
            header_value = response.headers.get(self.config.token_field)
            return header_value

        return None

    def get_auth_credentials(self) -> Dict[str, Dict[str, str]]:
        """Get current auth credentials to inject into a request.

        Returns:
            Dict with 'headers' and/or 'cookies' keys containing
            the credentials to merge into the request.
            Empty dict if not authenticated.
        """
        if not self.state.is_authenticated or not self.state.current_token:
            return {}

        token_value = f"{self.config.inject_prefix}{self.state.current_token}"

        if self.config.inject_as == InjectAs.HEADER:
            return {'headers': {self.config.inject_name: token_value}}
        elif self.config.inject_as == InjectAs.COOKIE:
            return {'cookies': {self.config.inject_name: token_value}}

        return {}

    def invalidate(self) -> None:
        """Mark current credentials as expired/invalid."""
        self.state.is_authenticated = False
        self.state.current_token = None

    def attempt_reauth(
        self,
        session: requests.Session,
        proxies: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
        timeout: int = 10
    ) -> bool:
        """Thread-safe re-authentication.

        Only one thread performs re-auth at a time. Other threads calling
        this method will block until the re-auth attempt completes, then
        return the result.

        Args:
            session: Requests session.
            proxies: Optional proxy config.
            verify_ssl: Whether to verify SSL.
            timeout: Request timeout.

        Returns:
            True if re-authentication succeeded.
        """
        with self._lock:
            # Check if another thread already re-authenticated successfully
            if self.state.is_authenticated and self.state.current_token:
                return True

            # Check retry limit
            if self.state.failed_auths >= self.config.max_retries:
                return False

            # Apply cooldown
            if self.config.cooldown > 0:
                time.sleep(self.config.cooldown)

            self.invalidate()

            try:
                return self.perform_login(
                    session,
                    proxies=proxies,
                    verify_ssl=verify_ssl,
                    timeout=timeout
                )
            except AuthenticationError:
                return False

    def is_auth_failure(self, status_code: int) -> bool:
        """Check if a status code indicates an authentication failure.

        Args:
            status_code: HTTP response status code.

        Returns:
            True if the status code is in the configured auth failure codes.
        """
        return status_code in self.config.auth_failure_codes

    def get_statistics(self) -> Dict[str, Any]:
        """Get authentication statistics.

        Returns:
            Dictionary with auth statistics.
        """
        return {
            'is_authenticated': self.state.is_authenticated,
            'auth_attempts': self.state.auth_attempts,
            'successful_auths': self.state.successful_auths,
            'failed_auths': self.state.failed_auths,
            'max_retries': self.config.max_retries,
            'auth_type': self.config.auth_type.value,
        }
