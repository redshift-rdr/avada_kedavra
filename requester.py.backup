# -*- coding: utf-8 -*-
import requests
import threading
import json
import argparse
import yaml
import copy
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, unquote_plus, quote_plus
from collections import defaultdict
from pathlib import Path
import sys # For platform check and stdin
import platform # For platform check

# Platform specific imports for non-blocking input
try:
    import msvcrt  # For Windows
except ImportError:
    msvcrt = None
    try:
        import tty
        import termios
        import select
    except ImportError:
        tty = None
        termios = None
        select = None

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.console import Group
from rich import box

# --- Global Variables ---
console = Console()
rich_lock = threading.Lock()
stop_requested = False # Flag to signal stopping continuous mode
original_terminal_settings = None # To restore terminal settings on Unix

# --- Results Table Definition (Moved outside main) ---
results_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
# ... (add columns as before) ...
results_table.add_column("ID", style="dim", width=6, justify="right")
results_table.add_column("Payload", max_width=30)
results_table.add_column("Method", width=8)
results_table.add_column("URL", max_width=50)
results_table.add_column("Status", width=8, justify="center")
results_table.add_column("Size (B)", width=10, justify="right")
results_table.add_column("Time (s)", width=10, justify="right")
results_table.add_column("Error", max_width=40)



# --- Helper Functions ---
def load_requests(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError: console.print(f"[bold red]Error:[/bold red] Input file not found: {filepath}"); exit(1)
    except json.JSONDecodeError as e: console.print(f"[bold red]Error:[/bold red] Invalid JSON in {filepath}: {e}"); exit(1)
    except Exception as e: console.print(f"[bold red]Error:[/bold red] Failed to load requests: {e}"); exit(1)

def load_config(filepath):
    if not filepath: return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if not isinstance(config, dict): console.print(f"[bold red]Error:[/bold red] Config file {filepath} must contain a dictionary."); exit(1)
            if 'rules' in config and not isinstance(config.get('rules'), list): console.print(f"[bold red]Error:[/bold red] 'rules' key in config must be a list."); exit(1)
            return config
    except FileNotFoundError: console.print(f"[bold red]Error:[/bold red] Config file not found: {filepath}"); exit(1)
    except yaml.YAMLError as e: console.print(f"[bold red]Error:[/bold red] Invalid YAML in {filepath}: {e}"); exit(1)
    except Exception as e: console.print(f"[bold red]Error:[/bold red] Failed to load config: {e}"); exit(1)

def load_payloads(payload_config):
    if not isinstance(payload_config, dict): console.print(f"[bold red]Error:[/bold red] Invalid 'payloads' section in rule."); return None
    payload_type = payload_config.get('type', 'list')
    source = payload_config.get('source')
    if source is None: console.print("[bold red]Error:[/bold red] 'source' missing in payload configuration."); return None

    payloads = []
    if payload_type == 'list':
        if not isinstance(source, list): console.print(f"[bold red]Error:[/bold red] Payload source must be a list for type 'list'."); return None
        payloads = [str(p) for p in source]
    elif payload_type == 'file':
        if not isinstance(source, str): console.print(f"[bold red]Error:[/bold red] Payload source must be a filename for type 'file'."); return None
        try:
            payload_path = Path(source)
            if not payload_path.is_file(): console.print(f"[bold red]Error:[/bold red] Payload file not found: {source}"); return None
            with open(payload_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                payloads = [line.strip() for line in f if line.strip()]
        except Exception as e: console.print(f"[bold red]Error:[/bold red] Failed to read payload file {source}: {e}"); return None
    elif payload_type == 'single':
         payloads = [str(source)]
    else:
        console.print(f"[bold red]Error:[/bold red] Unknown payload type: {payload_type}"); return None

    if not payloads: console.print(f"[bold yellow]Warning:[/bold yellow] No payloads loaded for rule (type: {payload_type}, source: {source}).")
    return payloads

def parse_raw_headers(header_list):
    headers = {}
    if not header_list or not isinstance(header_list, list): return headers
    for header_line in header_list[1:]:
        if not isinstance(header_line, str): continue
        if ':' in header_line:
            key, value = header_line.split(':', 1)
            headers[key.strip()] = value.strip()
        elif header_line.strip():
             console.print(f"[bold yellow]Warning:[/bold yellow] Header line without colon ignored: '{header_line.strip()}'")
    headers.pop('Host', None); headers.pop('Content-Length', None); headers.pop('Connection', None)
    headers.pop('Proxy-Connection', None); headers.pop('Cookie', None)
    return headers

def prepare_request_components(request_data):
    method = request_data.get('method', 'GET').upper()
    raw_url = request_data.get('url')
    if not raw_url or not isinstance(raw_url, str): return None

    headers = parse_raw_headers(request_data.get('headers', []))
    params_list = request_data.get('params', [])

    url_params = {}; cookies = {}; parsed_body_json = {}
    parsed_body_form = defaultdict(list); raw_body_content = None
    body_type = None; has_body_params = False

    content_type_header = headers.get('Content-Type', '').lower()
    is_json_content_type = 'application/json' in content_type_header
    is_form_content_type = 'application/x-www-form-urlencoded' in content_type_header
    is_multipart_content_type = 'multipart/form-data' in content_type_header

    if isinstance(params_list, list):
        for p in params_list:
            if not isinstance(p, dict): continue
            p_type = p.get('type'); p_name = p.get('name'); p_value = p.get('value', '')
            if not p_name and p_type not in ('body', 'json'): continue

            if p_type == 'url':
                if p_name: url_params[p_name] = str(p_value)
            elif p_type == 'cookie':
                if p_name: cookies[p_name] = str(p_value)
            elif p_type == 'json':
                has_body_params = True
                if body_type is None: body_type = 'json'
                elif body_type != 'json': console.print(f"[bold red]Error:[/bold red] Mixed body types ('{body_type}', 'json')."); return None
                if p_name: parsed_body_json[p_name] = p_value
            elif p_type == 'body':
                has_body_params = True
                if is_form_content_type or (body_type is None and not is_json_content_type and not is_multipart_content_type):
                    if body_type is None: body_type = 'form'
                    elif body_type != 'form': console.print(f"[bold red]Error:[/bold red] Mixed body types ('{body_type}', 'form')."); return None
                    if p_name: parsed_body_form[p_name].append(str(p_value))
                else: # Raw
                    if body_type is None: body_type = 'raw'
                    elif body_type != 'raw': console.print(f"[bold red]Error:[/bold red] Mixed body types ('{body_type}', 'raw/text')."); return None
                    raw_body_content = str(p_value) if p_value else str(p_name)
            elif p_type == 'multipart':
                 has_body_params = True
                 if body_type is None: body_type = 'multipart'
                 elif body_type not in ('multipart', 'raw'): console.print(f"[bold red]Error:[/bold red] Mixed body types ('{body_type}', 'multipart')."); return None
                 body_type = 'raw'; raw_body_content = request_data.get('body') # Assume raw multipart is in top-level body

    parsed_body = None; raw_body = None
    if body_type == 'json':
        parsed_body = parsed_body_json
        if not is_json_content_type: headers['Content-Type'] = 'application/json'
    elif body_type == 'form':
         parsed_body = dict(parsed_body_form)
         if not is_form_content_type: headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif body_type == 'raw':
         raw_body = raw_body_content

    try:
        parsed_url = urlparse(raw_url)
        if not parsed_url.scheme or not parsed_url.netloc: raise ValueError("URL scheme/netloc missing")
        existing_query_params = parse_qs(parsed_url.query)
    except ValueError as e: console.print(f"[bold red]Error:[/bold red] Failed to parse URL '{raw_url}': {e}"); return None

    final_query_params = defaultdict(list); final_url_params_dict = {}
    for k, v in existing_query_params.items(): final_query_params[k].extend(v)
    for k, v in url_params.items(): final_query_params[k] = [v]
    for k, v_list in final_query_params.items(): final_url_params_dict[k] = v_list[0] if len(v_list) == 1 else v_list
    base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, '', parsed_url.fragment))

    return { 'method': method, 'base_url': base_url, 'url_params': final_url_params_dict,
             'headers': headers, 'cookies': cookies, 'raw_body': raw_body, 'parsed_body': parsed_body,
             'body_type': body_type, 'has_body_params': has_body_params, 'original_data': request_data }

# --- request_matches_filter HELPER ---
def request_matches_filter(base_components, filter_config):
    if not filter_config or not isinstance(filter_config, dict): return True

    filter_method = filter_config.get('method')
    if filter_method:
        req_method = base_components.get('method', '').upper()
        methods_to_check = [m.upper() for m in filter_method] if isinstance(filter_method, list) else [filter_method.upper()]
        if req_method not in methods_to_check: return False

    filter_url_contains = filter_config.get('url_contains')
    if filter_url_contains:
        original_url = base_components.get('original_data', {}).get('url', '')
        if filter_url_contains not in original_url: return False

    filter_path_contains = filter_config.get('url_path_contains')
    if filter_path_contains:
        try:
            parsed_uri = urlparse(base_components.get('base_url', ''))
            if filter_path_contains not in parsed_uri.path: return False
        except Exception: return False # Fail safe

    filter_header_present = filter_config.get('header_present')
    if filter_header_present:
        header_found = any(hdr_name.lower() == filter_header_present.lower() for hdr_name in base_components.get('headers', {}))
        if not header_found: return False

    filter_header_value = filter_config.get('header_value_contains')
    if filter_header_value and isinstance(filter_header_value, dict):
        req_headers_lower = {k.lower(): v for k, v in base_components.get('headers', {}).items()}
        for filter_hdr_name, filter_hdr_substring in filter_header_value.items():
            filter_hdr_name_lower = filter_hdr_name.lower()
            if filter_hdr_name_lower not in req_headers_lower: return False
            if filter_hdr_substring not in req_headers_lower[filter_hdr_name_lower]: return False

    return True # All filters passed

# --- apply_modification (Returns tuple: components, success_bool) ---
def apply_modification(req_components, target_config, payload):
    if not target_config: return req_components, False
    components = copy.deepcopy(req_components)
    target_type = target_config.get('type'); target_name = target_config.get('name')
    if not target_type or not target_name: return components, False

    body_type = components.get('body_type')
    original_has_body_params = components.get('has_body_params', False)
    parsed_body = components.get('parsed_body')
    modification_successful = False

    if target_type == 'url':
        if target_name in components['url_params']: components['url_params'][target_name] = payload; modification_successful = True
    elif target_type == 'cookie':
        if target_name in components['cookies']: components['cookies'][target_name] = payload; modification_successful = True
    elif target_type == 'header':
        header_key_to_modify = next((k for k in components['headers'] if k.lower() == target_name.lower()), None)
        if header_key_to_modify: components['headers'][header_key_to_modify] = payload; modification_successful = True
    elif target_type == 'body':
        if original_has_body_params:
            if body_type == 'json' and isinstance(parsed_body, dict) and target_name in parsed_body:
                parsed_body[target_name] = payload; modification_successful = True
            elif body_type == 'form' and isinstance(parsed_body, dict) and target_name in parsed_body:
                parsed_body[target_name] = [payload]; modification_successful = True
            elif body_type != 'json' and body_type != 'form': # Raw or multipart fallback
                components['raw_body'] = payload; components['body_type'] = 'raw'; components['parsed_body'] = None; modification_successful = True
    # else: Unsupported target or conditions not met

    return components, modification_successful

# --- make_request_worker (Unchanged) ---
def make_request_worker(req_id, components, payload_str, session, config, live_table, progress, task_id, proxies):
    start_time = time.monotonic(); status_code = None; response_size = None; error_message = ""
    allow_redirects = config.get('allow_redirects', True); verify_ssl = config.get('verify_ssl', True); timeout = config.get('timeout', 10)
    display_url = components['base_url'] + ('?' + urlencode(components['url_params'], doseq=True) if components['url_params'] else '')

    try:
        request_args = { 'method': components['method'], 'url': components['base_url'], 'params': components['url_params'],
                         'headers': components['headers'], 'cookies': components['cookies'], 'allow_redirects': allow_redirects,
                         'verify': verify_ssl, 'timeout': timeout, 'proxies': proxies }
        body_type = components.get('body_type'); parsed_body = components.get('parsed_body'); raw_body = components.get('raw_body')

        if body_type == 'json' and parsed_body is not None:
            request_args['json'] = parsed_body
            if 'application/json' not in request_args['headers'].get('Content-Type','').lower(): request_args['headers']['Content-Type'] = 'application/json'
        elif body_type == 'form' and parsed_body is not None:
            try:
                form_data = urlencode(parsed_body, doseq=True); request_args['data'] = form_data.encode('utf-8')
                if 'application/x-www-form-urlencoded' not in request_args['headers'].get('Content-Type','').lower(): request_args['headers']['Content-Type'] = 'application/x-www-form-urlencoded'
            except Exception as e: console.print(f"[bold red]Error (Req {req_id}):[/bold red] Failed to serialize form body: {e}. Sending raw."); body_type = 'raw'; raw_body = str(parsed_body)
        if body_type in ('raw', 'multipart') and raw_body is not None:
             request_args['data'] = raw_body.encode('utf-8') if isinstance(raw_body, str) else raw_body

        response = session.request(**request_args)
        status_code = response.status_code; response_size = len(response.content) if response.content else 0
    except requests.exceptions.Timeout: error_message = "Timeout"
    except requests.exceptions.ProxyError as e: error_message = f"Proxy Error: {e}"
    except requests.exceptions.SSLError as e: error_message = f"SSL Error: {getattr(e, 'reason', e)}"
    except requests.exceptions.ConnectionError as e: error_message = f"Connection Err: {getattr(e, 'reason', e)}"
    except requests.exceptions.RequestException as e: error_message = f"Request Err: {e}"
    except Exception as e: error_message = f"Unexpected Err: {e}"

    duration = time.monotonic() - start_time
    with rich_lock:
        status_style = "white"
        if status_code:
            if 200 <= status_code < 300: status_style = "green"
            elif 300 <= status_code < 400: status_style = "yellow"
            elif 400 <= status_code < 500: status_style = "red"
            elif status_code >= 500: status_style = "bold red"
        payload_str_safe = (str(payload_str)[:27] + '...') if len(str(payload_str or '')) > 30 else str(payload_str or '-')
        display_url_short = (str(display_url)[:47] + '...') if len(str(display_url or '')) > 50 else str(display_url or '-')
        error_message_short = (str(error_message)[:37] + '...') if len(str(error_message or '')) > 40 else str(error_message or '')

        if hasattr(live_table, 'add_row'):
            live_table.add_row( str(req_id), payload_str_safe, components['method'], display_url_short,
                               f"[{status_style}]{status_code if status_code else 'ERR'}[/{status_style}]",
                               f"{response_size if response_size is not None else '-'}", f"{duration:.3f}",
                               f"[bright_red]{error_message_short}[/bright_red]" )
            if len(live_table.rows) > 1000:
                 try: live_table._rows = live_table._rows[-1000:]
                 except AttributeError: pass
        if hasattr(progress, 'update'): progress.update(task_id, advance=1)



# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Replay HTTP requests with modifications.")
    parser.add_argument("input_file", help="Path to the JSON file containing requests.")
    parser.add_argument("-c", "--config", help="Path to the YAML configuration file for modifications.")
    # ... (rest of args) ...
    parser.add_argument("-t", "--threads", type=int, default=5, help="Number of concurrent threads.")
    parser.add_argument("-d", "--delay", type=float, default=0, help="Delay (in seconds) between starting threads.")
    parser.add_argument('--timeout', type=int, help="Override request timeout in seconds.")
    parser.add_argument('--no-verify', action='store_true', help="Disable SSL certificate verification.")
    parser.add_argument('--no-redirects', action='store_true', help="Disable following redirects.")
    parser.add_argument("--proxy", help="HTTP/HTTPS proxy address (e.g., http://127.0.0.1:8080)")
    args = parser.parse_args()

    base_requests_data = load_requests(args.input_file)
    config = load_config(args.config) if args.config else {}

    config['timeout'] = args.timeout if args.timeout is not None else config.get('timeout', 10)
    config['verify_ssl'] = not args.no_verify if args.no_verify else config.get('verify_ssl', True)
    config['allow_redirects'] = not args.no_redirects if args.no_redirects else config.get('allow_redirects', True)
    num_threads = config.get('threads', args.threads); thread_delay = config.get('delay', args.delay)

    proxies = None
    if args.proxy:
        try: parsed_proxy = urlparse(args.proxy)
        except ValueError: console.print(f"[bold red]Error:[/bold red] Invalid proxy URL format: {args.proxy}"); exit(1)
        if not parsed_proxy.scheme or not parsed_proxy.netloc: console.print(f"[bold red]Error:[/bold red] Invalid proxy URL format: {args.proxy}"); exit(1)
        proxies = {"http": args.proxy, "https": args.proxy}; console.print(f"[cyan]Using proxy:[/cyan] {args.proxy}")
        if config.get('verify_ssl', True) and (parsed_proxy.hostname == '127.0.0.1' or parsed_proxy.hostname == 'localhost'):
             console.print("[bold yellow]Warning:[/bold yellow] Using local proxy with SSL verification. Consider '--no-verify'.")

    rules_list = config.get('rules', []) if isinstance(config.get('rules'), list) else []
    modifications_active = bool(rules_list)

    if modifications_active: console.print(f"[cyan]Found {len(rules_list)} modification rules. Filters and per-rule payloads active.[/cyan]")
    elif args.config: console.print("[yellow]Warning:[/yellow] Config has no 'rules' list. Replaying base requests.")
    else: console.print("[cyan]Info:[/cyan] No config specified. Replaying base requests.")

    tasks_to_run = []; request_id_counter = 1; skipped_filter_requests = 0; skipped_target_requests = 0; total_potential_requests = 0

    for base_request_data in base_requests_data:
        base_components = prepare_request_components(base_request_data)
        if base_components is None: continue # Skip requests that failed preparation

        if modifications_active:
            for rule_index, rule in enumerate(rules_list):
                target_config = rule.get('target')
                payload_config = rule.get('payloads')
                filter_config = rule.get('filter') # Get filter config

                if not target_config or not payload_config: continue # Skip invalid rules

                # --- Apply Filter ---
                if not request_matches_filter(base_components, filter_config):
                    # If filter doesn't match, skip this entire rule for this base request
                    # Count how many payload applications are skipped due to filter
                    payloads_for_rule_check = load_payloads(payload_config) # Need count for stats
                    if payloads_for_rule_check:
                         skipped_filter_requests += len(payloads_for_rule_check)
                         total_potential_requests += len(payloads_for_rule_check)
                    continue # Move to the next rule

                # --- Load Payloads and Apply Rule (Filter Passed) ---
                payloads_for_rule = load_payloads(payload_config)
                if payloads_for_rule is None or not payloads_for_rule: continue # Skip rule if no payloads

                for payload in payloads_for_rule:
                    total_potential_requests += 1
                    modified_components, success = apply_modification(
                        base_components, target_config, payload
                    )
                    if success:
                        tasks_to_run.append({ "id": request_id_counter, "components": modified_components, "payload_str": payload })
                        request_id_counter += 1
                    else:
                        skipped_target_requests += 1
        else:
            # No modifications active, just add base request
            tasks_to_run.append({ "id": request_id_counter, "components": base_components, "payload_str": "-" })
            request_id_counter += 1

    total_requests = len(tasks_to_run)
    if modifications_active:
        if skipped_filter_requests > 0:
            console.print(f"[yellow]Skipped {skipped_filter_requests} request iterations due to request filters.[/yellow]")
        if skipped_target_requests > 0:
            console.print(f"[yellow]Skipped {skipped_target_requests} request iterations where the specific rule target was not found (after filtering).[/yellow]")
        console.print(f"[cyan]Total potential modifications considered: {total_potential_requests}[/cyan]")


    if total_requests == 0:
        console.print("[bold red]Error:[/bold red] No requests generated to send.")
        return

    console.print(f"[cyan]Preparing to send {total_requests} requests using {num_threads} threads...[/cyan]")

    # ... (Progress bar setup, threading loop, completion message - unchanged) ...
    progress = Progress( SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(),
                         TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), TextColumn("({task.completed} of {task.total})"),
                         TimeRemainingColumn(), TimeElapsedColumn(), console=console )
    task_id = progress.add_task("[green]Sending Requests", total=total_requests)
    render_group = Group(progress, results_table)

    threads = []; task_index = 0
    with Live(render_group, refresh_per_second=10, console=console, vertical_overflow="visible") as live:
        session = requests.Session()
        while task_index < total_requests or any(t.is_alive() for t in threads):
            while task_index < total_requests and (threading.active_count() - 1 < num_threads):
                task_data = tasks_to_run[task_index]
                thread = threading.Thread( target=make_request_worker, args=(
                        task_data["id"], task_data["components"], task_data["payload_str"], session, config,
                        results_table, progress, task_id, proxies ), daemon=True )
                threads.append(thread); thread.start(); task_index += 1
                if thread_delay > 0: time.sleep(thread_delay)
            time.sleep(0.05)

    console.print(f"[bold green]Completed {total_requests} requests.[/bold green]")


if __name__ == "__main__":
    main()