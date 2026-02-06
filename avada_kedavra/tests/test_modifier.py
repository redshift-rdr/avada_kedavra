# -*- coding: utf-8 -*-
"""Tests for modifier module."""

import pytest
from avada_kedavra.core.modifier import apply_modification
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
