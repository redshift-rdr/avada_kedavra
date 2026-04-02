# -*- coding: utf-8 -*-
"""Data models for authentication configuration."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class AuthType(Enum):
    """Supported authentication types."""
    BEARER_TOKEN = "bearer_token"
    SESSION_COOKIE = "session_cookie"
    API_KEY = "api_key"


class TokenLocation(Enum):
    """Where to extract the token from in the login response."""
    BODY = "body"
    HEADER = "header"


class InjectAs(Enum):
    """How to inject credentials into outgoing requests."""
    HEADER = "header"
    COOKIE = "cookie"


@dataclass
class AuthConfig:
    """Authentication configuration parsed from YAML.

    Supports three auth types:
    - bearer_token: Login to an endpoint, extract a token from the response,
      inject it as a header (e.g., Authorization: Bearer <token>).
    - session_cookie: Login to an endpoint, extract a session cookie from the
      response, inject it into subsequent requests.
    - api_key: Static key injected into a header or cookie. No login endpoint
      needed, but re-authentication is not possible.
    """
    auth_type: AuthType

    # Login endpoint (required for bearer_token and session_cookie)
    login_url: Optional[str] = None
    login_method: str = "POST"
    credentials: Dict[str, Any] = field(default_factory=dict)
    credentials_format: str = "json"  # "json" or "form"

    # Token extraction from login response
    token_location: TokenLocation = TokenLocation.BODY
    token_field: str = "token"  # JSON field or header name

    # How to inject auth into requests
    inject_as: InjectAs = InjectAs.HEADER
    inject_name: str = "Authorization"  # Header or cookie name
    inject_prefix: str = ""  # e.g., "Bearer " for Authorization header

    # Static API key (only for api_key type)
    api_key: Optional[str] = None

    # Re-auth behavior
    max_retries: int = 3
    cooldown: float = 1.0  # Seconds between re-auth attempts

    # Status codes that trigger re-auth
    auth_failure_codes: list = field(default_factory=lambda: [401])

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.auth_type in (AuthType.BEARER_TOKEN, AuthType.SESSION_COOKIE):
            if not self.login_url:
                raise ValueError(
                    f"login_url is required for auth type '{self.auth_type.value}'"
                )
        if self.auth_type == AuthType.API_KEY:
            if not self.api_key:
                raise ValueError("api_key is required for auth type 'api_key'")


@dataclass
class AuthState:
    """Tracks current authentication state at runtime."""
    is_authenticated: bool = False
    current_token: Optional[str] = None
    auth_attempts: int = 0
    successful_auths: int = 0
    failed_auths: int = 0


def parse_auth_config(auth_data: Dict[str, Any]) -> AuthConfig:
    """Parse an auth config dict (from YAML) into an AuthConfig.

    Args:
        auth_data: Dictionary from the 'auth' key in YAML config.

    Returns:
        AuthConfig instance.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    raw_type = auth_data.get('type')
    if not raw_type:
        raise ValueError("auth.type is required (bearer_token, session_cookie, or api_key)")

    try:
        auth_type = AuthType(raw_type)
    except ValueError:
        valid = ', '.join(t.value for t in AuthType)
        raise ValueError(f"Invalid auth.type '{raw_type}'. Must be one of: {valid}")

    token_location_raw = auth_data.get('token_location', 'body')
    try:
        token_location = TokenLocation(token_location_raw)
    except ValueError:
        raise ValueError(f"Invalid token_location '{token_location_raw}'. Must be 'body' or 'header'")

    inject_as_raw = auth_data.get('inject_as', 'header')
    try:
        inject_as = InjectAs(inject_as_raw)
    except ValueError:
        raise ValueError(f"Invalid inject_as '{inject_as_raw}'. Must be 'header' or 'cookie'")

    auth_failure_codes = auth_data.get('auth_failure_codes', [401])
    if isinstance(auth_failure_codes, int):
        auth_failure_codes = [auth_failure_codes]

    return AuthConfig(
        auth_type=auth_type,
        login_url=auth_data.get('login_url'),
        login_method=auth_data.get('login_method', 'POST'),
        credentials=auth_data.get('credentials', {}),
        credentials_format=auth_data.get('credentials_format', 'json'),
        token_location=token_location,
        token_field=auth_data.get('token_field', 'token'),
        inject_as=inject_as,
        inject_name=auth_data.get('inject_name', 'Authorization'),
        inject_prefix=auth_data.get('inject_prefix', ''),
        api_key=auth_data.get('api_key'),
        max_retries=auth_data.get('max_retries', 3),
        cooldown=auth_data.get('cooldown', 1.0),
        auth_failure_codes=auth_failure_codes,
    )
