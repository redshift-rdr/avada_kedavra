# -*- coding: utf-8 -*-
"""HTTP request parsing and preparation."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs, urlunparse
from collections import defaultdict
from rich.console import Console

from ..models.request import RequestComponents
from ..utils.exceptions import RequestParsingError

console = Console()


def load_requests(filepath: str) -> List[Dict[str, Any]]:
    """Load requests from JSON file.

    Args:
        filepath: Path to JSON file containing request data.

    Returns:
        List of request dictionaries.

    Raises:
        RequestParsingError: If file not found, invalid JSON, or other errors.
    """
    try:
        file_path = Path(filepath)
        if not file_path.exists():
            raise RequestParsingError(f"Input file not found: {filepath}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    except FileNotFoundError:
        raise RequestParsingError(f"Input file not found: {filepath}")
    except json.JSONDecodeError as e:
        raise RequestParsingError(f"Invalid JSON in {filepath}: {e}")
    except Exception as e:
        raise RequestParsingError(f"Failed to load requests: {e}")


def parse_raw_headers(header_list: Optional[List[Any]]) -> Dict[str, str]:
    """Parse raw header lines into dictionary.

    Args:
        header_list: List of header strings (first element is request line).

    Returns:
        Dictionary of header name-value pairs.
    """
    headers: Dict[str, str] = {}

    if not header_list or not isinstance(header_list, list):
        return headers

    # Skip first line (request line), parse remaining headers
    for header_line in header_list[1:]:
        if not isinstance(header_line, str):
            continue

        if ':' in header_line:
            key, value = header_line.split(':', 1)
            headers[key.strip()] = value.strip()
        elif header_line.strip():
            console.print(f"[bold yellow]Warning:[/bold yellow] Header line without colon ignored: '{header_line.strip()}'")

    # Remove headers that should be auto-generated
    headers.pop('Host', None)
    headers.pop('Content-Length', None)
    headers.pop('Connection', None)
    headers.pop('Proxy-Connection', None)
    headers.pop('Cookie', None)

    return headers


def prepare_request_components(request_data: Dict[str, Any]) -> Optional[RequestComponents]:
    """Parse request data into structured components.

    Args:
        request_data: Dictionary containing raw request data.

    Returns:
        RequestComponents object or None if parsing fails.

    Raises:
        RequestParsingError: If request data is invalid or parsing fails.
    """
    method = request_data.get('method', 'GET').upper()
    raw_url = request_data.get('url')

    if not raw_url or not isinstance(raw_url, str):
        console.print("[bold red]Error:[/bold red] Missing or invalid URL in request.")
        return None

    headers = parse_raw_headers(request_data.get('headers', []))
    params_list = request_data.get('params', [])

    # Initialize component containers
    url_params: Dict[str, Any] = {}
    cookies: Dict[str, str] = {}
    parsed_body_json: Dict[str, Any] = {}
    parsed_body_form: Dict[str, List[str]] = defaultdict(list)
    raw_body_content: Optional[str] = None
    body_type: Optional[str] = None
    has_body_params = False

    # Detect content type
    content_type_header = headers.get('Content-Type', '').lower()
    is_json_content_type = 'application/json' in content_type_header
    is_form_content_type = 'application/x-www-form-urlencoded' in content_type_header
    is_multipart_content_type = 'multipart/form-data' in content_type_header

    # Parse parameters
    if isinstance(params_list, list):
        for p in params_list:
            if not isinstance(p, dict):
                continue

            p_type = p.get('type')
            p_name = p.get('name')
            p_value = p.get('value', '')

            if not p_name and p_type not in ('body', 'json'):
                continue

            if p_type == 'url':
                if p_name:
                    url_params[p_name] = str(p_value)

            elif p_type == 'cookie':
                if p_name:
                    cookies[p_name] = str(p_value)

            elif p_type == 'json':
                has_body_params = True
                if body_type is None:
                    body_type = 'json'
                elif body_type != 'json':
                    raise RequestParsingError(f"Mixed body types ('{body_type}', 'json').")
                if p_name:
                    parsed_body_json[p_name] = p_value

            elif p_type == 'body':
                has_body_params = True
                if is_form_content_type or (body_type is None and not is_json_content_type and not is_multipart_content_type):
                    if body_type is None:
                        body_type = 'form'
                    elif body_type != 'form':
                        raise RequestParsingError(f"Mixed body types ('{body_type}', 'form').")
                    if p_name:
                        parsed_body_form[p_name].append(str(p_value))
                else:  # Raw
                    if body_type is None:
                        body_type = 'raw'
                    elif body_type != 'raw':
                        raise RequestParsingError(f"Mixed body types ('{body_type}', 'raw/text').")
                    raw_body_content = str(p_value) if p_value else str(p_name)

            elif p_type == 'multipart':
                has_body_params = True
                if body_type is None:
                    body_type = 'multipart'
                elif body_type not in ('multipart', 'raw'):
                    raise RequestParsingError(f"Mixed body types ('{body_type}', 'multipart').")
                body_type = 'raw'
                raw_body_content = request_data.get('body')  # Assume raw multipart is in top-level body

    # Determine final body format
    parsed_body: Optional[Dict[str, Any]] = None
    raw_body: Optional[str] = None

    if body_type == 'json':
        parsed_body = parsed_body_json
        if not is_json_content_type:
            headers['Content-Type'] = 'application/json'
    elif body_type == 'form':
        parsed_body = dict(parsed_body_form)
        if not is_form_content_type:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif body_type == 'raw':
        raw_body = raw_body_content

    # Parse and validate URL
    try:
        parsed_url = urlparse(raw_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("URL scheme/netloc missing")
        existing_query_params = parse_qs(parsed_url.query)
    except ValueError as e:
        raise RequestParsingError(f"Failed to parse URL '{raw_url}': {e}")

    # Merge URL parameters
    final_query_params: Dict[str, List[str]] = defaultdict(list)
    final_url_params_dict: Dict[str, Any] = {}

    for k, v in existing_query_params.items():
        final_query_params[k].extend(v)
    for k, v in url_params.items():
        final_query_params[k] = [v]

    for k, v_list in final_query_params.items():
        final_url_params_dict[k] = v_list[0] if len(v_list) == 1 else v_list

    # Build base URL without query string
    base_url = urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        '',  # No query string in base URL
        parsed_url.fragment
    ))

    return RequestComponents(
        method=method,
        base_url=base_url,
        url_params=final_url_params_dict,
        headers=headers,
        cookies=cookies,
        raw_body=raw_body,
        parsed_body=parsed_body,
        body_type=body_type,  # type: ignore
        has_body_params=has_body_params,
        original_data=request_data
    )
