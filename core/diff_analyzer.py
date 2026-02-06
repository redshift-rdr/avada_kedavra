# -*- coding: utf-8 -*-
"""Differential analysis engine for comparing responses."""

import re
import difflib
from typing import List, Optional, Dict, Any
from ..models.baseline import BaselineResponse, DiffResult
from ..models.condition import ResponseData


class DifferentialAnalyzer:
    """Analyzes differences between baseline and fuzzed responses."""

    # Common error patterns to detect
    ERROR_PATTERNS = [
        r'error',
        r'exception',
        r'traceback',
        r'stack trace',
        r'fatal',
        r'warning',
        r'syntax error',
        r'mysql',
        r'postgresql',
        r'ora-\d+',  # Oracle errors
        r'sqlite',
        r'syntax.*near',
        r'unclosed.*quote',
        r'unexpected.*token',
        r'undefined.*index',
        r'division by zero',
        r'access.*denied',
        r'permission.*denied',
    ]

    def __init__(self, size_anomaly_threshold: float = 0.15, time_anomaly_threshold: float = 0.30):
        """Initialize differential analyzer.

        Args:
            size_anomaly_threshold: Percentage difference (0.15 = 15%) to consider size anomaly.
            time_anomaly_threshold: Percentage difference (0.30 = 30%) to consider time anomaly.
        """
        self.size_anomaly_threshold = size_anomaly_threshold
        self.time_anomaly_threshold = time_anomaly_threshold
        self.error_regex = re.compile('|'.join(self.ERROR_PATTERNS), re.IGNORECASE)

    def compare(
        self,
        baseline: BaselineResponse,
        response: ResponseData
    ) -> DiffResult:
        """Compare a response against its baseline.

        Args:
            baseline: The baseline response.
            response: The current response data.

        Returns:
            DiffResult containing detailed comparison.
        """
        # Calculate similarity ratio using difflib
        similarity = self._calculate_similarity(baseline.body, response.body)

        # Status code comparison
        status_code_diff = baseline.status_code != response.status_code

        # Size comparison
        size_diff_bytes = response.content_length - baseline.content_length
        size_diff_percent = self._calculate_percent_diff(
            baseline.content_length,
            response.content_length
        )

        # Time comparison
        time_diff_seconds = response.response_time - baseline.response_time
        time_diff_percent = self._calculate_percent_diff(
            baseline.response_time,
            response.response_time
        )

        # Body and header changes
        body_changed = baseline.body != response.body
        headers_changed = baseline.headers != response.headers

        # Detect anomalies
        is_size_anomaly = abs(size_diff_percent) > self.size_anomaly_threshold
        is_time_anomaly = abs(time_diff_percent) > self.time_anomaly_threshold

        # Detect new errors in response
        new_errors = self._find_new_errors(baseline.body, response.body)
        is_error_introduced = len(new_errors) > 0

        # Overall difference flag
        has_difference = (
            status_code_diff or
            body_changed or
            is_size_anomaly or
            is_time_anomaly or
            is_error_introduced
        )

        # Generate summary
        diff_summary = self._generate_summary(
            status_code_diff,
            size_diff_bytes,
            size_diff_percent,
            time_diff_percent,
            is_size_anomaly,
            is_time_anomaly,
            is_error_introduced,
            baseline.status_code,
            response.status_code
        )

        return DiffResult(
            has_difference=has_difference,
            similarity_ratio=similarity,
            status_code_diff=status_code_diff,
            size_diff_bytes=size_diff_bytes,
            size_diff_percent=size_diff_percent,
            time_diff_seconds=time_diff_seconds,
            time_diff_percent=time_diff_percent,
            body_changed=body_changed,
            headers_changed=headers_changed,
            is_size_anomaly=is_size_anomaly,
            is_time_anomaly=is_time_anomaly,
            is_error_introduced=is_error_introduced,
            new_errors=new_errors,
            diff_summary=diff_summary
        )

    def _calculate_similarity(self, baseline_body: str, response_body: str) -> float:
        """Calculate similarity ratio between two strings.

        Args:
            baseline_body: Baseline response body.
            response_body: Current response body.

        Returns:
            Similarity ratio from 0.0 to 1.0.
        """
        if not baseline_body and not response_body:
            return 1.0
        if not baseline_body or not response_body:
            return 0.0

        # Use SequenceMatcher for similarity
        matcher = difflib.SequenceMatcher(None, baseline_body, response_body)
        return matcher.ratio()

    def _calculate_percent_diff(self, baseline_val: float, current_val: float) -> float:
        """Calculate percentage difference.

        Args:
            baseline_val: Baseline value.
            current_val: Current value.

        Returns:
            Percentage difference (can be negative).
        """
        if baseline_val == 0:
            return 1.0 if current_val > 0 else 0.0

        return (current_val - baseline_val) / baseline_val

    def _find_new_errors(self, baseline_body: str, response_body: str) -> List[str]:
        """Find error patterns that appear in response but not in baseline.

        Args:
            baseline_body: Baseline response body.
            response_body: Current response body.

        Returns:
            List of new error messages found.
        """
        new_errors = []

        # Find all error matches in both
        baseline_errors = set(self.error_regex.findall(baseline_body.lower()))
        response_errors = set(self.error_regex.findall(response_body.lower()))

        # New errors are those in response but not in baseline
        new_error_types = response_errors - baseline_errors

        if new_error_types:
            # Extract actual error context (few words around match)
            for error_type in new_error_types:
                pattern = re.compile(rf'\b\w*{re.escape(error_type)}\w*\b.{{0,50}}', re.IGNORECASE)
                matches = pattern.findall(response_body)
                if matches:
                    # Take first match, truncate if too long
                    error_context = matches[0][:60]
                    new_errors.append(error_context)

        return new_errors

    def _generate_summary(
        self,
        status_diff: bool,
        size_diff_bytes: int,
        size_diff_percent: float,
        time_diff_percent: float,
        is_size_anomaly: bool,
        is_time_anomaly: bool,
        is_error: bool,
        baseline_status: int,
        current_status: int
    ) -> str:
        """Generate a compact summary of differences.

        Returns:
            Formatted summary string.
        """
        parts = []

        if status_diff:
            parts.append(f"Δ{baseline_status}→{current_status}")

        if is_size_anomaly:
            sign = "+" if size_diff_bytes > 0 else ""
            parts.append(f"Size{sign}{size_diff_bytes}B")

        if is_time_anomaly:
            sign = "+" if time_diff_percent > 0 else ""
            parts.append(f"Time{sign}{int(time_diff_percent*100)}%")

        if is_error:
            parts.append("ERR!")

        return " | ".join(parts) if parts else "No anomalies"


def create_request_id(method: str, url: str, body: str = "") -> str:
    """Create a unique request identifier for baseline matching.

    Args:
        method: HTTP method.
        url: Request URL.
        body: Request body.

    Returns:
        SHA256 hash of request components.
    """
    import hashlib
    request_str = f"{method.upper()}|{url}|{body}"
    return hashlib.sha256(request_str.encode('utf-8')).hexdigest()[:16]
