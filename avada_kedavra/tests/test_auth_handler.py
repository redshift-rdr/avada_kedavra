# -*- coding: utf-8 -*-
"""Tests for auth_handler module and auth config parsing."""

import threading
import pytest
from unittest.mock import MagicMock, patch

from avada_kedavra.models.auth import (
    AuthConfig, AuthType, AuthState, TokenLocation, InjectAs, parse_auth_config
)
from avada_kedavra.core.auth_handler import AuthHandler
from avada_kedavra.utils.exceptions import AuthenticationError


# --- Helpers ---

def make_mock_response(status_code=200, json_data=None, headers=None, text=""):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


def make_bearer_config(**overrides):
    """Create a standard bearer token AuthConfig for testing."""
    defaults = {
        'auth_type': AuthType.BEARER_TOKEN,
        'login_url': 'https://example.com/api/login',
        'credentials': {'username': 'admin', 'password': 'secret'},
        'token_field': 'token',
        'inject_prefix': 'Bearer ',
        'inject_name': 'Authorization',
    }
    defaults.update(overrides)
    return AuthConfig(**defaults)


def make_session(response):
    """Create a mock session that returns the given response."""
    session = MagicMock()
    session.request.return_value = response
    return session


# --- parse_auth_config tests ---

class TestParseAuthConfig:
    """Tests for parse_auth_config YAML parsing."""

    def test_valid_bearer_token(self):
        config = parse_auth_config({
            'type': 'bearer_token',
            'login_url': 'https://example.com/login',
            'credentials': {'user': 'admin', 'pass': 'pw'},
            'token_field': 'data.token',
            'inject_prefix': 'Bearer ',
        })
        assert config.auth_type == AuthType.BEARER_TOKEN
        assert config.login_url == 'https://example.com/login'
        assert config.token_field == 'data.token'
        assert config.inject_prefix == 'Bearer '

    def test_valid_session_cookie(self):
        config = parse_auth_config({
            'type': 'session_cookie',
            'login_url': 'https://example.com/login',
            'credentials': {'user': 'admin'},
            'inject_as': 'cookie',
            'inject_name': 'session_id',
            'token_location': 'header',
            'token_field': 'X-Session-Token',
        })
        assert config.auth_type == AuthType.SESSION_COOKIE
        assert config.inject_as == InjectAs.COOKIE
        assert config.token_location == TokenLocation.HEADER

    def test_valid_api_key(self):
        config = parse_auth_config({
            'type': 'api_key',
            'api_key': 'sk-12345',
            'inject_name': 'X-API-Key',
        })
        assert config.auth_type == AuthType.API_KEY
        assert config.api_key == 'sk-12345'

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="auth.type is required"):
            parse_auth_config({})

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid auth.type"):
            parse_auth_config({'type': 'oauth2'})

    def test_invalid_token_location_raises(self):
        with pytest.raises(ValueError, match="Invalid token_location"):
            parse_auth_config({
                'type': 'bearer_token',
                'login_url': 'https://example.com/login',
                'token_location': 'query_string',
            })

    def test_invalid_inject_as_raises(self):
        with pytest.raises(ValueError, match="Invalid inject_as"):
            parse_auth_config({
                'type': 'bearer_token',
                'login_url': 'https://example.com/login',
                'inject_as': 'query',
            })

    def test_auth_failure_codes_single_int(self):
        config = parse_auth_config({
            'type': 'bearer_token',
            'login_url': 'https://example.com/login',
            'auth_failure_codes': 401,
        })
        assert config.auth_failure_codes == [401]

    def test_auth_failure_codes_list(self):
        config = parse_auth_config({
            'type': 'bearer_token',
            'login_url': 'https://example.com/login',
            'auth_failure_codes': [401, 403],
        })
        assert config.auth_failure_codes == [401, 403]

    def test_defaults(self):
        config = parse_auth_config({
            'type': 'bearer_token',
            'login_url': 'https://example.com/login',
        })
        assert config.login_method == 'POST'
        assert config.credentials_format == 'json'
        assert config.token_location == TokenLocation.BODY
        assert config.token_field == 'token'
        assert config.inject_as == InjectAs.HEADER
        assert config.inject_name == 'Authorization'
        assert config.inject_prefix == ''
        assert config.max_retries == 3
        assert config.cooldown == 1.0


# --- AuthConfig validation tests ---

class TestAuthConfigValidation:
    """Tests for AuthConfig dataclass validation."""

    def test_bearer_token_requires_login_url(self):
        with pytest.raises(ValueError, match="login_url is required"):
            AuthConfig(auth_type=AuthType.BEARER_TOKEN)

    def test_session_cookie_requires_login_url(self):
        with pytest.raises(ValueError, match="login_url is required"):
            AuthConfig(auth_type=AuthType.SESSION_COOKIE)

    def test_api_key_requires_api_key(self):
        with pytest.raises(ValueError, match="api_key is required"):
            AuthConfig(auth_type=AuthType.API_KEY)

    def test_api_key_valid(self):
        config = AuthConfig(auth_type=AuthType.API_KEY, api_key="key123")
        assert config.api_key == "key123"


# --- AuthHandler.perform_login tests ---

class TestPerformLogin:
    """Tests for AuthHandler.perform_login."""

    def test_bearer_login_success(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        response = make_mock_response(200, json_data={'token': 'abc123'})
        session = make_session(response)

        result = handler.perform_login(session)

        assert result is True
        assert handler.state.is_authenticated is True
        assert handler.state.current_token == 'abc123'
        assert handler.state.successful_auths == 1
        session.request.assert_called_once()

    def test_bearer_login_nested_token(self):
        config = make_bearer_config(token_field='data.access_token')
        handler = AuthHandler(config)
        response = make_mock_response(200, json_data={
            'data': {'access_token': 'nested-token-456'}
        })
        session = make_session(response)

        result = handler.perform_login(session)

        assert result is True
        assert handler.state.current_token == 'nested-token-456'

    def test_bearer_login_deeply_nested_token(self):
        config = make_bearer_config(token_field='response.auth.jwt')
        handler = AuthHandler(config)
        response = make_mock_response(200, json_data={
            'response': {'auth': {'jwt': 'deep-token'}}
        })
        session = make_session(response)

        result = handler.perform_login(session)

        assert result is True
        assert handler.state.current_token == 'deep-token'

    def test_bearer_login_server_error(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        response = make_mock_response(500, text='Internal Server Error')
        session = make_session(response)

        with pytest.raises(AuthenticationError, match="Login failed with status 500"):
            handler.perform_login(session)

        assert handler.state.failed_auths == 1
        assert handler.state.is_authenticated is False

    def test_bearer_login_token_not_found(self):
        config = make_bearer_config(token_field='access_token')
        handler = AuthHandler(config)
        response = make_mock_response(200, json_data={'wrong_field': 'value'})
        session = make_session(response)

        with pytest.raises(AuthenticationError, match="Could not extract token"):
            handler.perform_login(session)

        assert handler.state.failed_auths == 1

    def test_bearer_login_non_json_response(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        # json() raises ValueError
        response = make_mock_response(200, json_data=None, text='not json')
        session = make_session(response)

        with pytest.raises(AuthenticationError, match="Could not extract token"):
            handler.perform_login(session)

    def test_header_token_extraction(self):
        config = make_bearer_config(
            token_location=TokenLocation.HEADER,
            token_field='X-Auth-Token',
        )
        handler = AuthHandler(config)
        response = make_mock_response(200, headers={'X-Auth-Token': 'header-tok'})
        session = make_session(response)

        result = handler.perform_login(session)

        assert result is True
        assert handler.state.current_token == 'header-tok'

    def test_header_token_not_found(self):
        config = make_bearer_config(
            token_location=TokenLocation.HEADER,
            token_field='X-Auth-Token',
        )
        handler = AuthHandler(config)
        response = make_mock_response(200, headers={'Other-Header': 'value'})
        session = make_session(response)

        with pytest.raises(AuthenticationError, match="Could not extract token"):
            handler.perform_login(session)

    def test_api_key_login(self):
        config = AuthConfig(auth_type=AuthType.API_KEY, api_key='my-key')
        handler = AuthHandler(config)
        session = make_session(None)  # Should not be called

        result = handler.perform_login(session)

        assert result is True
        assert handler.state.current_token == 'my-key'
        session.request.assert_not_called()

    def test_login_sends_json_credentials(self):
        config = make_bearer_config(credentials_format='json')
        handler = AuthHandler(config)
        response = make_mock_response(200, json_data={'token': 'tok'})
        session = make_session(response)

        handler.perform_login(session)

        call_kwargs = session.request.call_args
        assert call_kwargs.kwargs.get('json') or call_kwargs[1].get('json')

    def test_login_sends_form_credentials(self):
        config = make_bearer_config(credentials_format='form')
        handler = AuthHandler(config)
        response = make_mock_response(200, json_data={'token': 'tok'})
        session = make_session(response)

        handler.perform_login(session)

        call_kwargs = session.request.call_args
        assert call_kwargs.kwargs.get('data') or call_kwargs[1].get('data')

    def test_login_network_error(self):
        import requests as req_lib
        config = make_bearer_config()
        handler = AuthHandler(config)
        session = MagicMock()
        session.request.side_effect = req_lib.exceptions.ConnectionError("refused")

        with pytest.raises(AuthenticationError, match="Login request failed"):
            handler.perform_login(session)

        assert handler.state.failed_auths == 1

    def test_no_login_url_raises(self):
        config = AuthConfig(auth_type=AuthType.API_KEY, api_key='k')
        config.auth_type = AuthType.BEARER_TOKEN  # Force invalid state
        config.login_url = None
        handler = AuthHandler(config)
        session = make_session(None)

        with pytest.raises(AuthenticationError, match="No login URL"):
            handler.perform_login(session)


# --- AuthHandler.get_auth_credentials tests ---

class TestGetAuthCredentials:
    """Tests for credential injection."""

    def test_header_injection(self):
        config = make_bearer_config(inject_prefix='Bearer ')
        handler = AuthHandler(config)
        handler.state.is_authenticated = True
        handler.state.current_token = 'mytoken'

        creds = handler.get_auth_credentials()

        assert creds == {'headers': {'Authorization': 'Bearer mytoken'}}

    def test_cookie_injection(self):
        config = make_bearer_config(
            inject_as=InjectAs.COOKIE,
            inject_name='session',
            inject_prefix='',
        )
        handler = AuthHandler(config)
        handler.state.is_authenticated = True
        handler.state.current_token = 'sess-val'

        creds = handler.get_auth_credentials()

        assert creds == {'cookies': {'session': 'sess-val'}}

    def test_not_authenticated_returns_empty(self):
        config = make_bearer_config()
        handler = AuthHandler(config)

        creds = handler.get_auth_credentials()

        assert creds == {}

    def test_no_token_returns_empty(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        handler.state.is_authenticated = True
        handler.state.current_token = None

        creds = handler.get_auth_credentials()

        assert creds == {}


# --- AuthHandler.invalidate tests ---

class TestInvalidate:
    """Tests for credential invalidation."""

    def test_invalidate_clears_state(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        handler.state.is_authenticated = True
        handler.state.current_token = 'old-token'

        handler.invalidate()

        assert handler.state.is_authenticated is False
        assert handler.state.current_token is None


# --- AuthHandler.is_auth_failure tests ---

class TestIsAuthFailure:
    """Tests for auth failure detection."""

    def test_401_is_failure(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        assert handler.is_auth_failure(401) is True

    def test_200_is_not_failure(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        assert handler.is_auth_failure(200) is False

    def test_custom_failure_codes(self):
        config = make_bearer_config(auth_failure_codes=[401, 403, 407])
        handler = AuthHandler(config)
        assert handler.is_auth_failure(403) is True
        assert handler.is_auth_failure(407) is True
        assert handler.is_auth_failure(500) is False


# --- AuthHandler.attempt_reauth tests ---

class TestAttemptReauth:
    """Tests for thread-safe re-authentication."""

    def test_reauth_success(self):
        config = make_bearer_config(cooldown=0)
        handler = AuthHandler(config)
        handler.state.is_authenticated = False

        response = make_mock_response(200, json_data={'token': 'new-token'})
        session = make_session(response)

        result = handler.attempt_reauth(session)

        assert result is True
        assert handler.state.current_token == 'new-token'
        assert handler.state.is_authenticated is True

    def test_reauth_skips_if_already_authenticated(self):
        config = make_bearer_config(cooldown=0)
        handler = AuthHandler(config)
        handler.state.is_authenticated = True
        handler.state.current_token = 'existing-token'

        session = make_session(None)

        result = handler.attempt_reauth(session)

        assert result is True
        session.request.assert_not_called()

    def test_reauth_respects_max_retries(self):
        config = make_bearer_config(max_retries=2, cooldown=0)
        handler = AuthHandler(config)
        handler.state.failed_auths = 2  # Already at max

        session = make_session(None)

        result = handler.attempt_reauth(session)

        assert result is False
        session.request.assert_not_called()

    def test_reauth_failure_returns_false(self):
        config = make_bearer_config(cooldown=0)
        handler = AuthHandler(config)
        handler.state.is_authenticated = False

        response = make_mock_response(401, text='Unauthorized')
        session = make_session(response)

        result = handler.attempt_reauth(session)

        assert result is False

    def test_reauth_thread_safety(self):
        """Test that only one thread performs re-auth at a time."""
        config = make_bearer_config(cooldown=0)
        handler = AuthHandler(config)
        handler.state.is_authenticated = False

        call_count = {'value': 0}
        original_perform_login = handler.perform_login

        def counting_login(*args, **kwargs):
            call_count['value'] += 1
            return original_perform_login(*args, **kwargs)

        response = make_mock_response(200, json_data={'token': 'tok'})
        session = make_session(response)

        results = []

        def reauth_worker():
            # Reset auth state to trigger actual login attempt
            with handler._lock:
                was_authed = handler.state.is_authenticated
            result = handler.attempt_reauth(session)
            results.append(result)

        handler.perform_login = counting_login

        threads = [threading.Thread(target=reauth_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # All threads should report success
        assert all(r is True for r in results)
        # But only one actual login should have occurred (others see is_authenticated=True)
        # The first thread logs in, the rest see the token and skip
        assert call_count['value'] == 1


# --- AuthHandler.get_statistics tests ---

class TestGetStatistics:
    """Tests for statistics reporting."""

    def test_initial_statistics(self):
        config = make_bearer_config()
        handler = AuthHandler(config)

        stats = handler.get_statistics()

        assert stats['is_authenticated'] is False
        assert stats['auth_attempts'] == 0
        assert stats['successful_auths'] == 0
        assert stats['failed_auths'] == 0
        assert stats['auth_type'] == 'bearer_token'
        assert stats['max_retries'] == 3

    def test_statistics_after_login(self):
        config = make_bearer_config()
        handler = AuthHandler(config)
        response = make_mock_response(200, json_data={'token': 'tok'})
        session = make_session(response)

        handler.perform_login(session)
        stats = handler.get_statistics()

        assert stats['is_authenticated'] is True
        assert stats['auth_attempts'] == 1
        assert stats['successful_auths'] == 1
