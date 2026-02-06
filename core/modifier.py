# -*- coding: utf-8 -*-
"""Request modification logic."""

import copy
from typing import Dict, Optional, Tuple, Any

from ..models.request import RequestComponents


def apply_modification(
    req_components: RequestComponents,
    target_config: Optional[Dict[str, str]],
    payload: str
) -> Tuple[RequestComponents, bool]:
    """Apply a payload modification to request components.

    Args:
        req_components: The original request components.
        target_config: Dictionary with 'type' and optionally 'name' specifying modification target.
        payload: The payload value to inject.

    Returns:
        Tuple of (modified_components, success_flag).
        success_flag is True if modification was successfully applied.
    """
    if not target_config:
        return req_components, False

    # Deep copy to avoid modifying original
    components = copy.deepcopy(req_components)

    target_type = target_config.get('type')
    target_name = target_config.get('name')

    # HTTP method doesn't require a 'name' field
    if not target_type:
        return components, False

    # For non-method types, name is required
    if target_type != 'method' and not target_name:
        return components, False

    modification_successful = False

    # Modify HTTP method
    if target_type == 'method':
        # Validate HTTP method
        valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT']
        method_upper = payload.upper()

        if method_upper in valid_methods:
            components.method = method_upper
            modification_successful = True

    # Modify URL parameter
    elif target_type == 'url':
        if target_name in components.url_params:
            components.url_params[target_name] = payload
            modification_successful = True

    # Modify cookie
    elif target_type == 'cookie':
        if target_name in components.cookies:
            components.cookies[target_name] = payload
            modification_successful = True

    # Modify header (case-insensitive lookup)
    elif target_type == 'header':
        header_key_to_modify = next(
            (k for k in components.headers if k.lower() == target_name.lower()),
            None
        )
        if header_key_to_modify:
            components.headers[header_key_to_modify] = payload
            modification_successful = True

    # Modify body parameter
    elif target_type == 'body':
        if components.has_body_params:
            body_type = components.body_type
            parsed_body = components.parsed_body

            # JSON body modification
            if body_type == 'json' and isinstance(parsed_body, dict) and target_name in parsed_body:
                parsed_body[target_name] = payload
                modification_successful = True

            # Form body modification
            elif body_type == 'form' and isinstance(parsed_body, dict) and target_name in parsed_body:
                parsed_body[target_name] = [payload]
                modification_successful = True

            # Raw/multipart fallback - replace entire body
            elif body_type not in ('json', 'form'):
                components.raw_body = payload
                components.body_type = 'raw'
                components.parsed_body = None
                modification_successful = True

    return components, modification_successful
