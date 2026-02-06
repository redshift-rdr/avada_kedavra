# -*- coding: utf-8 -*-
"""Response condition checking logic."""

import re
from typing import List, Dict, Any, Optional

from ..models.condition import ResponseData, ConditionResult, ConditionType


def check_conditions(
    response_data: ResponseData,
    conditions: Optional[Dict[str, Any]]
) -> List[ConditionResult]:
    """Check all configured conditions against response data.

    Args:
        response_data: Captured response data.
        conditions: Dictionary of conditions to check.
                   Special key 'match_mode' can be 'all' or 'any' (default: 'any')
                   - 'any': Return all matching conditions (OR logic)
                   - 'all': Only return results if ALL conditions match (AND logic)

    Returns:
        List of ConditionResult objects for matched conditions.
        Empty list if no matches or if match_mode='all' and not all conditions matched.
    """
    if not conditions or not isinstance(conditions, dict):
        return []

    # Extract match mode (default to 'any' for backward compatibility)
    match_mode = conditions.get('match_mode', 'any').lower()

    results: List[ConditionResult] = []
    total_conditions = 0  # Track total conditions to check

    # Check string in body
    if "string_in_body" in conditions:
        total_conditions += 1
        search_string = str(conditions["string_in_body"])
        if search_string in response_data.body:
            results.append(ConditionResult(
                matched=True,
                condition_type="string_in_body",
                description=f"Body:'{search_string[:15]}'",
                value=search_string
            ))

    # Check string in headers
    if "string_in_headers" in conditions:
        total_conditions += 1
        search_string = str(conditions["string_in_headers"])
        headers_str = str(response_data.headers)
        if search_string in headers_str:
            results.append(ConditionResult(
                matched=True,
                condition_type="string_in_headers",
                description=f"Hdr:'{search_string[:10]}'",
                value=search_string
            ))

    # Check regex in body
    if "regex_in_body" in conditions:
        total_conditions += 1
        pattern = str(conditions["regex_in_body"])
        try:
            if re.search(pattern, response_data.body):
                results.append(ConditionResult(
                    matched=True,
                    condition_type="regex_in_body",
                    description=f"Regex(body)",
                    value=pattern
                ))
        except re.error:
            pass  # Invalid regex, skip

    # Check regex in headers
    if "regex_in_headers" in conditions:
        total_conditions += 1
        pattern = str(conditions["regex_in_headers"])
        headers_str = str(response_data.headers)
        try:
            if re.search(pattern, headers_str):
                results.append(ConditionResult(
                    matched=True,
                    condition_type="regex_in_headers",
                    description=f"Regex(hdr)",
                    value=pattern
                ))
        except re.error:
            pass  # Invalid regex, skip

    # Check status code
    if "status_code" in conditions:
        total_conditions += 1
        expected_codes = conditions["status_code"]
        if not isinstance(expected_codes, list):
            expected_codes = [expected_codes]

        if response_data.status_code in expected_codes:
            results.append(ConditionResult(
                matched=True,
                condition_type="status_code",
                description=f"Status={response_data.status_code}",
                value=response_data.status_code
            ))

    # Check content length greater than
    if "content_length_gt" in conditions:
        total_conditions += 1
        threshold = int(conditions["content_length_gt"])
        if response_data.content_length > threshold:
            results.append(ConditionResult(
                matched=True,
                condition_type="content_length_gt",
                description=f"Size>{threshold}",
                value=response_data.content_length
            ))

    # Check content length less than
    if "content_length_lt" in conditions:
        total_conditions += 1
        threshold = int(conditions["content_length_lt"])
        if response_data.content_length < threshold:
            results.append(ConditionResult(
                matched=True,
                condition_type="content_length_lt",
                description=f"Size<{threshold}",
                value=response_data.content_length
            ))

    # Check content length equal to
    if "content_length_eq" in conditions:
        total_conditions += 1
        expected = int(conditions["content_length_eq"])
        if response_data.content_length == expected:
            results.append(ConditionResult(
                matched=True,
                condition_type="content_length_eq",
                description=f"Size={expected}",
                value=response_data.content_length
            ))

    # Check response time greater than
    if "response_time_gt" in conditions:
        total_conditions += 1
        threshold = float(conditions["response_time_gt"])
        if response_data.response_time > threshold:
            results.append(ConditionResult(
                matched=True,
                condition_type="response_time_gt",
                description=f"Time>{threshold}s",
                value=response_data.response_time
            ))

    # Check response time less than
    if "response_time_lt" in conditions:
        total_conditions += 1
        threshold = float(conditions["response_time_lt"])
        if response_data.response_time < threshold:
            results.append(ConditionResult(
                matched=True,
                condition_type="response_time_lt",
                description=f"Time<{threshold}s",
                value=response_data.response_time
            ))

    # Apply match mode logic
    if match_mode == 'all':
        # For 'all' mode: only return results if ALL conditions matched
        if len(results) == total_conditions and total_conditions > 0:
            return results
        else:
            return []  # Not all conditions matched, return empty
    else:
        # For 'any' mode (default): return all matched conditions
        return results


def format_condition_matches(condition_results: List[ConditionResult]) -> str:
    """Format condition results for display.

    Args:
        condition_results: List of condition check results.

    Returns:
        Formatted string showing all matched conditions.
    """
    if not condition_results:
        return ""

    # Create compact summary
    summaries = []
    for result in condition_results:
        if result.matched:
            # Truncate long descriptions for compact display
            desc = result.description
            if len(desc) > 25:
                desc = desc[:22] + "..."
            summaries.append(desc)

    if not summaries:
        return ""

    # Join with pipe separator for compact display, limit total length
    formatted = " | ".join(summaries)
    if len(formatted) > 45:
        formatted = formatted[:42] + "..."

    return formatted
