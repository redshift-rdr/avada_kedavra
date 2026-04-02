# -*- coding: utf-8 -*-
"""HTTP request execution."""

import time
import threading
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List
import requests
from rich.progress import Progress
from rich.table import Table

from ..models.request import RequestComponents, AppConfig
from ..models.condition import ResponseData
from ..models.baseline import BaselineResponse
from ..core.condition_checker import check_conditions, format_condition_matches
from ..core.diff_analyzer import DifferentialAnalyzer, create_request_id
from ..core.reflection_detector import ReflectionDetector
from ..core.rate_limiter import RateLimiter
from ..core.auth_handler import AuthHandler


def make_request_worker(
    req_id: int,
    components: RequestComponents,
    payload_str: str,
    session: requests.Session,
    config: AppConfig,
    live_table: Table,
    progress: Progress,
    task_id: Any,
    proxies: Optional[Dict[str, str]],
    rich_lock: threading.Lock,
    conditions: Optional[Dict[str, Any]] = None,
    results_collector: Optional[List[Dict[str, Any]]] = None,
    baseline_store: Optional[Any] = None,
    diff_analyzer: Optional[DifferentialAnalyzer] = None,
    reflection_detector: Optional[ReflectionDetector] = None,
    rate_limiter: Optional[RateLimiter] = None,
    baseline_mode: bool = False,
    base_components: Optional[RequestComponents] = None,
    baseline_miss_counter: Optional[Dict[str, int]] = None,
    auth_handler: Optional[AuthHandler] = None,
    continue_on_auth_errors: bool = False,
    auth_error_event: Optional[threading.Event] = None
) -> None:
    """Execute a single HTTP request in a worker thread.

    Args:
        req_id: Unique request ID for tracking.
        components: Request components to send (may be modified).
        payload_str: String representation of the payload (for display).
        session: Requests session for connection pooling.
        config: Application configuration.
        live_table: Rich table for displaying results.
        progress: Rich progress bar.
        task_id: Progress task ID.
        proxies: Proxy configuration dict.
        rich_lock: Threading lock for rich console updates.
        conditions: Optional response conditions to check.
        results_collector: Optional list to collect results for export.
        baseline_store: Optional baseline store for diff analysis.
        diff_analyzer: Optional differential analyzer.
        reflection_detector: Optional reflection detector.
        rate_limiter: Optional rate limiter for adaptive throttling.
        baseline_mode: Whether running in baseline capture mode.
        base_components: Optional original (unmodified) components for baseline matching.
        baseline_miss_counter: Optional dict to track baseline matching failures.
        auth_handler: Optional auth handler for credential injection and re-auth.
        continue_on_auth_errors: If True, 401s without auth config are logged but don't pause.
        auth_error_event: Optional threading Event set when unhandled 401 is detected (signals main loop).
    """
    start_time = time.monotonic()
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    error_message = ""
    response_body = ""
    response_headers: Dict[str, str] = {}

    # Build display URL
    display_url = components.base_url
    if components.url_params:
        display_url += '?' + urlencode(components.url_params, doseq=True)

    auth_display = ""

    def _build_request_args() -> Dict[str, Any]:
        """Build request arguments, injecting auth credentials if available."""
        args: Dict[str, Any] = {
            'method': components.method,
            'url': components.base_url,
            'params': components.url_params,
            'headers': dict(components.headers),  # Copy so auth injection doesn't mutate
            'cookies': dict(components.cookies),
            'allow_redirects': config.allow_redirects,
            'verify': config.verify_ssl,
            'timeout': config.timeout,
            'proxies': proxies
        }

        # Inject auth credentials
        if auth_handler:
            auth_creds = auth_handler.get_auth_credentials()
            if 'headers' in auth_creds:
                args['headers'].update(auth_creds['headers'])
            if 'cookies' in auth_creds:
                args['cookies'].update(auth_creds['cookies'])

        return args

    def _apply_body(args: Dict[str, Any]) -> None:
        """Apply body data to request arguments."""
        nonlocal error_message
        body_type = components.body_type
        parsed_body = components.parsed_body
        raw_body = components.raw_body

        if body_type == 'json' and parsed_body is not None:
            args['json'] = parsed_body
            if 'application/json' not in args['headers'].get('Content-Type', '').lower():
                args['headers']['Content-Type'] = 'application/json'
        elif body_type == 'form' and parsed_body is not None:
            try:
                form_data = urlencode(parsed_body, doseq=True)
                args['data'] = form_data.encode('utf-8')
                if 'application/x-www-form-urlencoded' not in args['headers'].get('Content-Type', '').lower():
                    args['headers']['Content-Type'] = 'application/x-www-form-urlencoded'
            except Exception as e:
                error_message = f"Failed to serialize form body: {e}. Sending raw."
                body_type_fallback = 'raw'
                raw_body_fallback = str(parsed_body)
                args['data'] = raw_body_fallback.encode('utf-8')
                return

        if body_type in ('raw', 'multipart') and raw_body is not None:
            args['data'] = raw_body.encode('utf-8') if isinstance(raw_body, str) else raw_body

    def _execute_request() -> None:
        """Execute the HTTP request and capture response data."""
        nonlocal status_code, response_size, error_message, response_body, response_headers

        request_args = _build_request_args()
        _apply_body(request_args)

        response = session.request(**request_args)
        status_code = response.status_code
        response_size = len(response.content) if response.content else 0

        try:
            response_body = response.text
        except Exception:
            response_body = ""

        response_headers = dict(response.headers)

    try:
        _execute_request()

        # Auth failure detection and re-auth retry
        if status_code and auth_handler and auth_handler.is_auth_failure(status_code):
            # Attempt re-authentication (thread-safe: only one thread re-auths)
            reauth_ok = auth_handler.attempt_reauth(
                session,
                proxies=proxies,
                verify_ssl=config.verify_ssl,
                timeout=config.timeout
            )
            if reauth_ok:
                # Retry the request with fresh credentials
                status_code = None
                response_size = None
                response_body = ""
                response_headers = {}
                error_message = ""
                _execute_request()
                auth_display = "[RE-AUTH OK]"
            else:
                auth_display = "[AUTH FAILED]"
                error_message = f"{error_message} [AUTH FAILED]" if error_message else "Auth failed - max retries exceeded"

        elif status_code and not auth_handler and status_code in (401, 403):
            # No auth handler configured — signal unhandled auth error
            if continue_on_auth_errors:
                auth_display = "[401 AUTH ERROR]"
            elif auth_error_event is not None:
                auth_error_event.set()
                auth_display = "[AUTH ERROR - PAUSED]"

    except requests.exceptions.Timeout:
        error_message = "Timeout"
    except requests.exceptions.ProxyError as e:
        error_message = f"Proxy Error: {e}"
    except requests.exceptions.SSLError as e:
        error_message = f"SSL Error: {getattr(e, 'reason', e)}"
    except requests.exceptions.ConnectionError as e:
        error_message = f"Connection Err: {getattr(e, 'reason', e)}"
    except requests.exceptions.RequestException as e:
        error_message = f"Request Err: {e}"
    except Exception as e:
        error_message = f"Unexpected Err: {e}"

    duration = time.monotonic() - start_time

    # Create response data for analysis
    response_data = ResponseData(
        status_code=status_code,
        headers=response_headers,
        body=response_body,
        content_length=response_size if response_size else 0,
        response_time=duration,
        error=error_message
    )

    # Phase 1 Feature: Rate Limiting Detection
    if rate_limiter and status_code:
        is_rate_limited = rate_limiter.check_response(status_code, response_body, response_headers)
        if is_rate_limited:
            error_message = f"{error_message} [RATE LIMITED]" if error_message else "Rate limited"
            # Apply adaptive delay for next request
            rate_limiter.apply_delay()

    # Phase 1 Feature: WAF Detection (one-time check on first error)
    waf_detected = None
    if rate_limiter and status_code and status_code >= 400:
        waf_detected = rate_limiter.detect_waf(response_body, response_headers)

    # Generate request ID for baseline matching using ORIGINAL components
    # This ensures all modified versions of the same request share the same baseline
    baseline_components = base_components if base_components else components
    request_body_str = baseline_components.raw_body if baseline_components.raw_body else str(baseline_components.parsed_body or "")
    req_baseline_id = create_request_id(
        baseline_components.method,
        baseline_components.base_url,
        request_body_str
    )

    # Phase 1 Feature: Baseline Mode - Capture baseline responses
    if baseline_mode and baseline_store and status_code:
        baseline_resp = BaselineResponse(
            request_id=req_baseline_id,
            status_code=status_code,
            content_length=response_size if response_size else 0,
            response_time=duration,
            body=response_body,
            headers=response_headers
        )
        baseline_store.add_baseline(baseline_resp)

    # Phase 1 Feature: Differential Analysis
    diff_display = ""
    baseline_not_found = False
    if diff_analyzer and baseline_store and not baseline_mode:
        baseline = baseline_store.get_baseline(req_baseline_id)
        if baseline:
            diff_result = diff_analyzer.compare(baseline, response_data)
            if diff_result.has_difference:
                diff_display = diff_result.diff_summary
        else:
            # Baseline not found - this is important to know
            baseline_not_found = True
            diff_display = "NO_BASELINE"
            # Increment counter in a thread-safe way
            if baseline_miss_counter is not None:
                with rich_lock:
                    baseline_miss_counter['count'] += 1

    # Phase 1 Feature: Reflection Detection
    reflection_display = ""
    if reflection_detector and payload_str != "-" and status_code:
        reflection_match = reflection_detector.detect_reflection(
            str(payload_str),
            response_body,
            response_headers
        )
        if reflection_match:
            reflection_display = reflection_detector.format_reflection_result(reflection_match)

    # Check response conditions if configured
    condition_match_display = ""
    if conditions and status_code:
        condition_results = check_conditions(response_data, conditions)
        condition_match_display = format_condition_matches(condition_results)

    # Update display table and progress
    with rich_lock:
        # Determine status color
        status_style = "white"
        if status_code:
            if 200 <= status_code < 300:
                status_style = "green"
            elif 300 <= status_code < 400:
                status_style = "yellow"
            elif 400 <= status_code < 500:
                status_style = "red"
            elif status_code >= 500:
                status_style = "bold red"

        # Truncate long strings for display
        payload_str_safe = (str(payload_str)[:27] + '...') if len(str(payload_str or '')) > 30 else str(payload_str or '-')
        display_url_short = (str(display_url)[:47] + '...') if len(str(display_url or '')) > 50 else str(display_url or '-')
        error_message_short = (str(error_message)[:37] + '...') if len(str(error_message or '')) > 40 else str(error_message or '')

        # Combine all analysis displays (Phase 1 features + conditions)
        analysis_parts = []

        if error_message_short:
            analysis_parts.append(f"[bright_red]{error_message_short}[/bright_red]")

        if waf_detected:
            analysis_parts.append(f"[bold yellow]WAF:{waf_detected}[/bold yellow]")

        if diff_display:
            if baseline_not_found:
                analysis_parts.append(f"[bold yellow]⚠️ {diff_display}[/bold yellow]")
            else:
                analysis_parts.append(f"[bold cyan]{diff_display}[/bold cyan]")

        if reflection_display:
            analysis_parts.append(f"[bold magenta]{reflection_display}[/bold magenta]")

        if condition_match_display:
            analysis_parts.append(f"[bold green]✓ {condition_match_display}[/bold green]")

        if auth_display:
            if "FAILED" in auth_display or "ERROR" in auth_display:
                analysis_parts.append(f"[bold red]{auth_display}[/bold red]")
            else:
                analysis_parts.append(f"[bold cyan]{auth_display}[/bold cyan]")

        combined_display = " | ".join(analysis_parts) if analysis_parts else ""

        # Add row to results table
        if hasattr(live_table, 'add_row'):
            live_table.add_row(
                str(req_id),
                payload_str_safe,
                components.method,
                display_url_short,
                f"[{status_style}]{status_code if status_code else 'ERR'}[/{status_style}]",
                f"{response_size if response_size is not None else '-'}",
                f"{duration:.3f}",
                combined_display
            )

            # Limit table size to prevent memory issues
            if len(live_table.rows) > 1000:
                try:
                    live_table._rows = live_table._rows[-1000:]
                except AttributeError:
                    pass

        # Update progress bar
        if hasattr(progress, 'update'):
            progress.update(task_id, advance=1)

        # Collect result data for export if collector provided
        if results_collector is not None:
            result_data = {
                'id': req_id,
                'payload': payload_str,
                'method': components.method,
                'url': display_url,
                'status_code': status_code if status_code else '',
                'content_length': response_size if response_size is not None else '',
                'response_time': f"{duration:.3f}",
                'error': error_message,
                'conditions_matched': condition_match_display,
                'diff_analysis': diff_display,
                'reflection_detected': reflection_display,
                'waf_detected': waf_detected if waf_detected else '',
                'auth_status': auth_display
            }
            results_collector.append(result_data)
