# -*- coding: utf-8 -*-
"""Request modification logic."""

import copy
from typing import Dict, List, Optional, Tuple, Any

from ..models.request import RequestComponents


def is_wildcard_target(target_config) -> bool:
    """Check if a target config represents a wildcard (all parameters).

    A wildcard target means the rule should apply to all injectable parameters.
    This is true when:
    - target_config is None (omitted from rule)
    - target_config is the string "*"
    - target_config is a dict with name: "*"

    Args:
        target_config: The target configuration from a rule.

    Returns:
        True if this is a wildcard target.
    """
    if target_config is None:
        return True
    if target_config == '*':
        return True
    if isinstance(target_config, dict) and target_config.get('name') == '*':
        return True
    return False


def collect_all_targets(
    components: RequestComponents,
    target_type: Optional[str] = None
) -> List[Dict[str, str]]:
    """Collect all injectable parameter targets from request components.

    When no target is specified or a wildcard is used, this function enumerates
    all parameters in the request that can be targeted for payload injection.

    Args:
        components: The request components to extract targets from.
        target_type: Optional type filter. If set, only returns targets of that type.
            Valid values: 'url', 'cookie', 'header', 'body'.

    Returns:
        List of target config dicts, each with 'type' and 'name' keys.
    """
    targets: List[Dict[str, str]] = []

    if target_type is None or target_type == 'url':
        for name in components.url_params:
            targets.append({"type": "url", "name": name})

    if target_type is None or target_type == 'cookie':
        for name in components.cookies:
            targets.append({"type": "cookie", "name": name})

    if target_type is None or target_type == 'header':
        for name in components.headers:
            targets.append({"type": "header", "name": name})

    if target_type is None or target_type == 'body':
        if components.has_body_params and components.parsed_body and isinstance(components.parsed_body, dict):
            for name in components.parsed_body:
                targets.append({"type": "body", "name": name})

    return targets


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
