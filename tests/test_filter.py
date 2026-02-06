# -*- coding: utf-8 -*-
"""Tests for filter module."""

import pytest
from avada_kedavra.core.filter import request_matches_filter
from avada_kedavra.models.request import RequestComponents


class TestRequestMatchesFilter:
    """Tests for request_matches_filter function."""

    def test_no_filter_returns_true(self):
        """Test that no filter matches all requests."""
        components = RequestComponents(method="GET", base_url="https://example.com")
        assert request_matches_filter(components, None) is True
        assert request_matches_filter(components, {}) is True

    def test_method_filter_single_match(self):
        """Test method filter with single value matches."""
        components = RequestComponents(method="POST", base_url="https://example.com")
        filter_config = {"method": "POST"}
        assert request_matches_filter(components, filter_config) is True

    def test_method_filter_single_no_match(self):
        """Test method filter with single value doesn't match."""
        components = RequestComponents(method="GET", base_url="https://example.com")
        filter_config = {"method": "POST"}
        assert request_matches_filter(components, filter_config) is False

    def test_method_filter_list_match(self):
        """Test method filter with list of values matches."""
        components = RequestComponents(method="PUT", base_url="https://example.com")
        filter_config = {"method": ["GET", "POST", "PUT"]}
        assert request_matches_filter(components, filter_config) is True

    def test_method_filter_case_insensitive(self):
        """Test method filter is case-insensitive."""
        components = RequestComponents(method="post", base_url="https://example.com")
        filter_config = {"method": "POST"}
        assert request_matches_filter(components, filter_config) is True

    def test_url_contains_match(self):
        """Test url_contains filter matches."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            original_data={"url": "https://example.com/api/users/123"}
        )
        filter_config = {"url_contains": "/api/users/"}
        assert request_matches_filter(components, filter_config) is True

    def test_url_contains_no_match(self):
        """Test url_contains filter doesn't match."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            original_data={"url": "https://example.com/products"}
        )
        filter_config = {"url_contains": "/api/users/"}
        assert request_matches_filter(components, filter_config) is False

    def test_url_path_contains_match(self):
        """Test url_path_contains filter matches."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com/api/search"
        )
        filter_config = {"url_path_contains": "/api/"}
        assert request_matches_filter(components, filter_config) is True

    def test_url_path_contains_no_match(self):
        """Test url_path_contains filter doesn't match."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com/products"
        )
        filter_config = {"url_path_contains": "/api/"}
        assert request_matches_filter(components, filter_config) is False

    def test_header_present_match(self):
        """Test header_present filter matches."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"Authorization": "Bearer token123", "Content-Type": "application/json"}
        )
        filter_config = {"header_present": "Authorization"}
        assert request_matches_filter(components, filter_config) is True

    def test_header_present_case_insensitive(self):
        """Test header_present filter is case-insensitive."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"authorization": "Bearer token123"}
        )
        filter_config = {"header_present": "Authorization"}
        assert request_matches_filter(components, filter_config) is True

    def test_header_present_no_match(self):
        """Test header_present filter doesn't match."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"Content-Type": "application/json"}
        )
        filter_config = {"header_present": "Authorization"}
        assert request_matches_filter(components, filter_config) is False

    def test_header_value_contains_match(self):
        """Test header_value_contains filter matches."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        filter_config = {"header_value_contains": {"Content-Type": "json"}}
        assert request_matches_filter(components, filter_config) is True

    def test_header_value_contains_no_match(self):
        """Test header_value_contains filter doesn't match."""
        components = RequestComponents(
            method="GET",
            base_url="https://example.com",
            headers={"Content-Type": "text/html"}
        )
        filter_config = {"header_value_contains": {"Content-Type": "json"}}
        assert request_matches_filter(components, filter_config) is False

    def test_multiple_filters_all_match(self):
        """Test multiple filters all match."""
        components = RequestComponents(
            method="POST",
            base_url="https://example.com/api/users",
            headers={"Content-Type": "application/json"},
            original_data={"url": "https://example.com/api/users"}
        )
        filter_config = {
            "method": "POST",
            "url_contains": "/api/",
            "header_present": "Content-Type"
        }
        assert request_matches_filter(components, filter_config) is True

    def test_multiple_filters_one_fails(self):
        """Test multiple filters with one not matching returns False."""
        components = RequestComponents(
            method="POST",
            base_url="https://example.com/api/users",
            headers={"User-Agent": "test"},
            original_data={"url": "https://example.com/api/users"}
        )
        filter_config = {
            "method": "POST",
            "url_contains": "/api/",
            "header_present": "Authorization"  # This doesn't match
        }
        assert request_matches_filter(components, filter_config) is False

    def test_invalid_url_path_returns_false(self):
        """Test that invalid URL path fails safely."""
        components = RequestComponents(
            method="GET",
            base_url=""  # Invalid URL
        )
        filter_config = {"url_path_contains": "/api/"}
        # Should not crash, should return False
        assert request_matches_filter(components, filter_config) is False
