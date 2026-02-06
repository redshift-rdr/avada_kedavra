# -*- coding: utf-8 -*-
"""Tests for condition_checker module."""

import pytest
from avada_kedavra.core.condition_checker import check_conditions, format_condition_matches
from avada_kedavra.models.condition import ResponseData, ConditionResult


class TestCheckConditions:
    """Tests for check_conditions function."""

    def test_no_conditions_returns_empty(self):
        """Test that no conditions returns empty list."""
        response_data = ResponseData(status_code=200, body="test")
        result = check_conditions(response_data, None)
        assert result == []

    def test_empty_conditions_returns_empty(self):
        """Test that empty conditions dict returns empty list."""
        response_data = ResponseData(status_code=200, body="test")
        result = check_conditions(response_data, {})
        assert result == []

    def test_string_in_body_match(self):
        """Test string_in_body condition matches."""
        response_data = ResponseData(status_code=200, body="This contains error message")
        conditions = {"string_in_body": "error"}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].matched is True
        assert results[0].condition_type == "string_in_body"

    def test_string_in_body_no_match(self):
        """Test string_in_body condition doesn't match."""
        response_data = ResponseData(status_code=200, body="This is fine")
        conditions = {"string_in_body": "error"}
        results = check_conditions(response_data, conditions)

        assert len(results) == 0

    def test_string_in_headers_match(self):
        """Test string_in_headers condition matches."""
        response_data = ResponseData(
            status_code=200,
            headers={"X-Debug": "true", "Server": "nginx"}
        )
        conditions = {"string_in_headers": "X-Debug"}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].condition_type == "string_in_headers"

    def test_regex_in_body_match(self):
        """Test regex_in_body condition matches."""
        response_data = ResponseData(status_code=200, body="SQL error: syntax error")
        conditions = {"regex_in_body": "error|exception|fault"}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].condition_type == "regex_in_body"

    def test_regex_in_body_invalid_pattern(self):
        """Test regex_in_body with invalid pattern is silently skipped."""
        response_data = ResponseData(status_code=200, body="test")
        conditions = {"regex_in_body": "[invalid(regex"}
        results = check_conditions(response_data, conditions)

        assert len(results) == 0

    def test_status_code_single_match(self):
        """Test status_code condition with single value."""
        response_data = ResponseData(status_code=200)
        conditions = {"status_code": 200}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].value == 200

    def test_status_code_list_match(self):
        """Test status_code condition with list of values."""
        response_data = ResponseData(status_code=404)
        conditions = {"status_code": [200, 404, 500]}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].value == 404

    def test_status_code_no_match(self):
        """Test status_code condition doesn't match."""
        response_data = ResponseData(status_code=500)
        conditions = {"status_code": [200, 201]}
        results = check_conditions(response_data, conditions)

        assert len(results) == 0

    def test_content_length_gt_match(self):
        """Test content_length_gt condition matches."""
        response_data = ResponseData(content_length=1500)
        conditions = {"content_length_gt": 1000}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].condition_type == "content_length_gt"

    def test_content_length_lt_match(self):
        """Test content_length_lt condition matches."""
        response_data = ResponseData(content_length=500)
        conditions = {"content_length_lt": 1000}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].condition_type == "content_length_lt"

    def test_content_length_eq_match(self):
        """Test content_length_eq condition matches."""
        response_data = ResponseData(content_length=1000)
        conditions = {"content_length_eq": 1000}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].condition_type == "content_length_eq"

    def test_response_time_gt_match(self):
        """Test response_time_gt condition matches."""
        response_data = ResponseData(response_time=2.5)
        conditions = {"response_time_gt": 2.0}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].condition_type == "response_time_gt"

    def test_response_time_lt_match(self):
        """Test response_time_lt condition matches."""
        response_data = ResponseData(response_time=0.5)
        conditions = {"response_time_lt": 1.0}
        results = check_conditions(response_data, conditions)

        assert len(results) == 1
        assert results[0].condition_type == "response_time_lt"

    def test_match_mode_any_partial_matches(self):
        """Test match_mode 'any' returns partial matches."""
        response_data = ResponseData(
            status_code=200,
            body="success",
            content_length=500
        )
        conditions = {
            "match_mode": "any",
            "status_code": 200,
            "string_in_body": "success",
            "content_length_gt": 10000  # This won't match
        }
        results = check_conditions(response_data, conditions)

        # Should return 2 matches (status and body, not size)
        assert len(results) == 2

    def test_match_mode_all_partial_matches_returns_empty(self):
        """Test match_mode 'all' with partial matches returns empty."""
        response_data = ResponseData(
            status_code=200,
            body="success",
            content_length=500
        )
        conditions = {
            "match_mode": "all",
            "status_code": 200,
            "string_in_body": "success",
            "content_length_gt": 10000  # This won't match
        }
        results = check_conditions(response_data, conditions)

        # Should return empty because not all matched
        assert len(results) == 0

    def test_match_mode_all_complete_match(self):
        """Test match_mode 'all' with all conditions matching."""
        response_data = ResponseData(
            status_code=200,
            body="success",
            content_length=500
        )
        conditions = {
            "match_mode": "all",
            "status_code": 200,
            "string_in_body": "success",
            "content_length_gt": 100
        }
        results = check_conditions(response_data, conditions)

        # Should return all 3 results
        assert len(results) == 3

    def test_multiple_conditions_any_mode(self):
        """Test multiple conditions with any mode (default)."""
        response_data = ResponseData(
            status_code=500,
            body="SQL error: syntax error near",
            content_length=1500,
            response_time=2.5
        )
        conditions = {
            "regex_in_body": "error|exception",
            "status_code": 500,
            "content_length_gt": 1000,
            "response_time_gt": 2.0
        }
        results = check_conditions(response_data, conditions)

        # All 4 should match
        assert len(results) == 4


class TestFormatConditionMatches:
    """Tests for format_condition_matches function."""

    def test_empty_results_returns_empty_string(self):
        """Test that empty results returns empty string."""
        assert format_condition_matches([]) == ""

    def test_single_result_formatted(self):
        """Test single result is formatted correctly."""
        result = ConditionResult(
            matched=True,
            condition_type="status_code",
            description="Status=200"
        )
        formatted = format_condition_matches([result])
        assert "Status=200" in formatted

    def test_multiple_results_pipe_separated(self):
        """Test multiple results are pipe-separated."""
        results = [
            ConditionResult(matched=True, condition_type="status", description="Status=200"),
            ConditionResult(matched=True, condition_type="body", description="Body:'error'"),
        ]
        formatted = format_condition_matches(results)
        assert "|" in formatted
        assert "Status=200" in formatted
        assert "Body:'error'" in formatted

    def test_long_descriptions_truncated(self):
        """Test that long descriptions are truncated."""
        result = ConditionResult(
            matched=True,
            condition_type="test",
            description="A" * 50  # Very long description
        )
        formatted = format_condition_matches([result])
        assert len(formatted) <= 45 + 3  # Max length + "..."

    def test_unmatched_results_ignored(self):
        """Test that unmatched results are not included."""
        results = [
            ConditionResult(matched=True, condition_type="test", description="Matched"),
            ConditionResult(matched=False, condition_type="test", description="Not matched"),
        ]
        formatted = format_condition_matches(results)
        assert "Matched" in formatted
        assert "Not matched" not in formatted
