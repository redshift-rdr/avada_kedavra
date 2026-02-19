# -*- coding: utf-8 -*-
"""Tests for modifier module."""

import pytest
from avada_kedavra.core.modifier import apply_modification, is_wildcard_target, collect_all_targets
from avada_kedavra.models.request import RequestComponents


class TestApplyModification:
    """Tests for apply_modification function."""

    def test_no_target_config_returns_unchanged(self):
        """Test that no target config returns original components."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            url_params={"id": "123"}
        )
        modified, success = apply_modification(original, None, "payload")

        assert success is False
        assert modified.url_params["id"] == "123"

    def test_invalid_target_config_returns_unchanged(self):
        """Test that invalid target config returns original components."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            url_params={"id": "123"}
        )
        # Missing 'name' key
        target_config = {"type": "url"}
        modified, success = apply_modification(original, target_config, "payload")

        assert success is False

    def test_url_param_modification_success(self):
        """Test successful URL parameter modification."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            url_params={"id": "123", "page": "1"}
        )
        target_config = {"type": "url", "name": "id"}
        modified, success = apply_modification(original, target_config, "999")

        assert success is True
        assert modified.url_params["id"] == "999"
        assert modified.url_params["page"] == "1"  # Other params unchanged
        assert original.url_params["id"] == "123"  # Original unchanged

    def test_url_param_modification_param_not_exists(self):
        """Test URL parameter modification when param doesn't exist."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            url_params={"page": "1"}
        )
        target_config = {"type": "url", "name": "id"}
        modified, success = apply_modification(original, target_config, "999")

        assert success is False

    def test_cookie_modification_success(self):
        """Test successful cookie modification."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            cookies={"session_id": "abc123", "token": "xyz"}
        )
        target_config = {"type": "cookie", "name": "session_id"}
        modified, success = apply_modification(original, target_config, "new_session")

        assert success is True
        assert modified.cookies["session_id"] == "new_session"
        assert modified.cookies["token"] == "xyz"

    def test_header_modification_success(self):
        """Test successful header modification."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"User-Agent": "old", "Accept": "application/json"}
        )
        target_config = {"type": "header", "name": "User-Agent"}
        modified, success = apply_modification(original, target_config, "Mozilla/5.0")

        assert success is True
        assert modified.headers["User-Agent"] == "Mozilla/5.0"
        assert modified.headers["Accept"] == "application/json"

    def test_header_modification_case_insensitive(self):
        """Test header modification is case-insensitive."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"user-agent": "old"}
        )
        target_config = {"type": "header", "name": "User-Agent"}
        modified, success = apply_modification(original, target_config, "new")

        assert success is True
        assert modified.headers["user-agent"] == "new"

    def test_json_body_modification_success(self):
        """Test successful JSON body modification."""
        original = RequestComponents(
            method="POST",
            base_url="https://example.com",
            body_type="json",
            parsed_body={"username": "admin", "password": "pass123"},
            has_body_params=True
        )
        target_config = {"type": "body", "name": "username"}
        modified, success = apply_modification(original, target_config, "hacker")

        assert success is True
        assert modified.parsed_body["username"] == "hacker"
        assert modified.parsed_body["password"] == "pass123"

    def test_form_body_modification_success(self):
        """Test successful form body modification."""
        original = RequestComponents(
            method="POST",
            base_url="https://example.com",
            body_type="form",
            parsed_body={"email": "test@example.com", "name": "Test"},
            has_body_params=True
        )
        target_config = {"type": "body", "name": "email"}
        modified, success = apply_modification(original, target_config, "new@example.com")

        assert success is True
        assert modified.parsed_body["email"] == ["new@example.com"]
        assert modified.parsed_body["name"] == "Test"

    def test_raw_body_modification_success(self):
        """Test successful raw body modification."""
        original = RequestComponents(
            method="POST",
            base_url="https://example.com",
            body_type="raw",
            raw_body="original body content",
            has_body_params=True
        )
        target_config = {"type": "body", "name": "anything"}
        modified, success = apply_modification(original, target_config, "new body")

        assert success is True
        assert modified.raw_body == "new body"
        assert modified.body_type == "raw"
        assert modified.parsed_body is None

    def test_body_modification_no_body_params(self):
        """Test body modification when request has no body params."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            has_body_params=False
        )
        target_config = {"type": "body", "name": "test"}
        modified, success = apply_modification(original, target_config, "payload")

        assert success is False

    def test_body_modification_param_not_exists(self):
        """Test body modification when parameter doesn't exist."""
        original = RequestComponents(
            method="POST",
            base_url="https://example.com",
            body_type="json",
            parsed_body={"username": "admin"},
            has_body_params=True
        )
        target_config = {"type": "body", "name": "password"}
        modified, success = apply_modification(original, target_config, "payload")

        assert success is False

    def test_deep_copy_preserves_original(self):
        """Test that modification doesn't affect original components."""
        original = RequestComponents(
            method="GET",
            base_url="https://example.com",
            url_params={"id": "123"}
        )
        target_config = {"type": "url", "name": "id"}
        modified, success = apply_modification(original, target_config, "999")

        assert success is True
        assert modified.url_params["id"] == "999"
        assert original.url_params["id"] == "123"  # Original unchanged
        # Ensure they're different objects
        assert modified is not original
        assert modified.url_params is not original.url_params


class TestIsWildcardTarget:
    """Tests for is_wildcard_target function."""

    def test_none_is_wildcard(self):
        """Test that None target is a wildcard."""
        assert is_wildcard_target(None) is True

    def test_star_string_is_wildcard(self):
        """Test that '*' string is a wildcard."""
        assert is_wildcard_target('*') is True

    def test_dict_with_star_name_is_wildcard(self):
        """Test that dict with name='*' is a wildcard."""
        assert is_wildcard_target({"type": "body", "name": "*"}) is True

    def test_dict_with_only_star_name_is_wildcard(self):
        """Test that dict with only name='*' is a wildcard."""
        assert is_wildcard_target({"name": "*"}) is True

    def test_normal_target_is_not_wildcard(self):
        """Test that a normal target config is not a wildcard."""
        assert is_wildcard_target({"type": "url", "name": "id"}) is False

    def test_empty_dict_is_not_wildcard(self):
        """Test that an empty dict is not a wildcard."""
        assert is_wildcard_target({}) is False

    def test_method_target_is_not_wildcard(self):
        """Test that a method target is not a wildcard."""
        assert is_wildcard_target({"type": "method"}) is False


class TestCollectAllTargets:
    """Tests for collect_all_targets function."""

    def test_collects_url_params(self):
        """Test collecting URL parameters."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            url_params={"id": "123", "page": "1"}
        )
        targets = collect_all_targets(components)
        url_targets = [t for t in targets if t["type"] == "url"]
        assert len(url_targets) == 2
        assert {"type": "url", "name": "id"} in url_targets
        assert {"type": "url", "name": "page"} in url_targets

    def test_collects_cookies(self):
        """Test collecting cookie parameters."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            cookies={"session": "abc", "token": "xyz"}
        )
        targets = collect_all_targets(components)
        cookie_targets = [t for t in targets if t["type"] == "cookie"]
        assert len(cookie_targets) == 2
        assert {"type": "cookie", "name": "session"} in cookie_targets
        assert {"type": "cookie", "name": "token"} in cookie_targets

    def test_collects_headers(self):
        """Test collecting header parameters."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"User-Agent": "test", "Accept": "application/json"}
        )
        targets = collect_all_targets(components)
        header_targets = [t for t in targets if t["type"] == "header"]
        assert len(header_targets) == 2
        assert {"type": "header", "name": "User-Agent"} in header_targets
        assert {"type": "header", "name": "Accept"} in header_targets

    def test_collects_body_params(self):
        """Test collecting body parameters."""
        components = RequestComponents(
            method="POST",
            base_url="https://example.com",
            body_type="json",
            parsed_body={"username": "admin", "password": "secret"},
            has_body_params=True
        )
        targets = collect_all_targets(components)
        body_targets = [t for t in targets if t["type"] == "body"]
        assert len(body_targets) == 2
        assert {"type": "body", "name": "username"} in body_targets
        assert {"type": "body", "name": "password"} in body_targets

    def test_collects_all_param_types(self):
        """Test collecting all parameter types from a rich request."""
        components = RequestComponents(
            method="POST",
            base_url="https://example.com",
            url_params={"id": "1"},
            headers={"Authorization": "Bearer tok"},
            cookies={"session": "abc"},
            body_type="json",
            parsed_body={"email": "test@test.com"},
            has_body_params=True
        )
        targets = collect_all_targets(components)
        assert len(targets) == 4
        types = [t["type"] for t in targets]
        assert "url" in types
        assert "cookie" in types
        assert "header" in types
        assert "body" in types

    def test_filter_by_type_url(self):
        """Test filtering targets to only URL params."""
        components = RequestComponents(
            method="POST",
            base_url="https://example.com",
            url_params={"id": "1", "page": "2"},
            cookies={"session": "abc"},
            body_type="json",
            parsed_body={"email": "test@test.com"},
            has_body_params=True
        )
        targets = collect_all_targets(components, target_type="url")
        assert len(targets) == 2
        assert all(t["type"] == "url" for t in targets)

    def test_filter_by_type_body(self):
        """Test filtering targets to only body params."""
        components = RequestComponents(
            method="POST",
            base_url="https://example.com",
            url_params={"id": "1"},
            body_type="json",
            parsed_body={"username": "admin", "password": "secret"},
            has_body_params=True
        )
        targets = collect_all_targets(components, target_type="body")
        assert len(targets) == 2
        assert all(t["type"] == "body" for t in targets)

    def test_empty_request_returns_empty(self):
        """Test that a request with no params returns no targets."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com"
        )
        targets = collect_all_targets(components)
        assert targets == []

    def test_no_body_targets_when_no_body_params(self):
        """Test that body targets are not collected when has_body_params is False."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            has_body_params=False,
            parsed_body=None
        )
        targets = collect_all_targets(components, target_type="body")
        assert targets == []

    def test_no_body_targets_when_raw_body(self):
        """Test that raw body does not produce named targets."""
        components = RequestComponents(
            method="POST",
            base_url="https://example.com",
            body_type="raw",
            raw_body="some raw data",
            has_body_params=True,
            parsed_body=None
        )
        targets = collect_all_targets(components, target_type="body")
        assert targets == []
