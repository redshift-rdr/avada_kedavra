# -*- coding: utf-8 -*-
"""Request filtering logic."""

from typing import Optional, Dict, Any
from urllib.parse import urlparse

from ..models.request import RequestComponents


def request_matches_filter(components: RequestComponents, filter_config: Optional[Dict[str, Any]]) -> bool:
    """Check if a request matches the given filter criteria.

    Args:
        components: The request components to check.
        filter_config: Dictionary containing filter criteria (method, url_contains, etc.).

    Returns:
        True if request matches all filter criteria, False otherwise.
    """
    if not filter_config or not isinstance(filter_config, dict):
        return True  # No filter means all requests match

    # Filter by HTTP method
    filter_method = filter_config.get('method')
    if filter_method:
        req_method = components.method.upper()
        methods_to_check = [m.upper() for m in filter_method] if isinstance(filter_method, list) else [filter_method.upper()]
        if req_method not in methods_to_check:
            return False

    # Filter by URL substring
    filter_url_contains = filter_config.get('url_contains')
    if filter_url_contains:
        original_url = components.original_data.get('url', '')
        if filter_url_contains not in original_url:
            return False

    # Filter by URL path substring
    filter_path_contains = filter_config.get('url_path_contains')
    if filter_path_contains:
        try:
            parsed_uri = urlparse(components.base_url)
            if filter_path_contains not in parsed_uri.path:
                return False
        except Exception:
            return False  # Fail safe

    # Filter by header presence
    filter_header_present = filter_config.get('header_present')
    if filter_header_present:
        header_found = any(
            hdr_name.lower() == filter_header_present.lower()
            for hdr_name in components.headers
        )
        if not header_found:
            return False

    # Filter by header value substring
    filter_header_value = filter_config.get('header_value_contains')
    if filter_header_value and isinstance(filter_header_value, dict):
        req_headers_lower = {k.lower(): v for k, v in components.headers.items()}
        for filter_hdr_name, filter_hdr_substring in filter_header_value.items():
            filter_hdr_name_lower = filter_hdr_name.lower()
            if filter_hdr_name_lower not in req_headers_lower:
                return False
            if filter_hdr_substring not in req_headers_lower[filter_hdr_name_lower]:
                return False

    return True  # All filters passed
