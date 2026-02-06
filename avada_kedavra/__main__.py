# -*- coding: utf-8 -*-
"""Main entry point for avada_kedavra HTTP request fuzzing tool."""

import sys
import time
import threading
import argparse
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional

import requests
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

from .core.config import load_config, merge_cli_args
from .core.request_parser import load_requests, prepare_request_components
from .core.payload_loader import load_payloads
from .core.filter import request_matches_filter
from .core.modifier import apply_modification
from .network.requester import make_request_worker
from .ui.console import console, create_results_table
from .models.request import TaskData
from .utils.exceptions import (
    AvadaKedavraError,
    ConfigurationError,
    RequestParsingError,
    PayloadLoadError
)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="HTTP request replay and fuzzing tool for security testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s requests.json -c config.yaml
  %(prog)s requests.json -c config.yaml --proxy http://127.0.0.1:8080
  %(prog)s requests.json -c config.yaml -t 10 -d 0.1 --no-verify
        """
    )

    # Required arguments
    parser.add_argument(
        "input_file",
        help="Path to the JSON file containing requests"
    )

    # Optional configuration
    parser.add_argument(
        "-c", "--config",
        help="Path to the YAML configuration file for modifications"
    )

    # Performance options
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=5,
        help="Number of concurrent threads (default: 5)"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=0,
        help="Delay in seconds between starting threads (default: 0)"
    )

    # Network options
    parser.add_argument(
        '--timeout',
        type=int,
        help="Override request timeout in seconds (default: 10)"
    )
    parser.add_argument(
        '--no-verify',
        action='store_true',
        help="Disable SSL certificate verification"
    )
    parser.add_argument(
        '--no-redirects',
        action='store_true',
        help="Disable following redirects"
    )
    parser.add_argument(
        "--proxy",
        help="HTTP/HTTPS proxy address (e.g., http://127.0.0.1:8080)"
    )

    # Output options
    parser.add_argument(
        "-o", "--output",
        help="Save results to file (format determined by extension: .json, .csv, .html)"
    )

    # Phase 1 Security Testing Features
    parser.add_argument(
        "--baseline-mode",
        action="store_true",
        help="Run in baseline mode: capture baseline responses without fuzzing"
    )
    parser.add_argument(
        "--baseline-file",
        default="baselines.json",
        help="Path to baseline file for saving/loading (default: baselines.json)"
    )
    parser.add_argument(
        "--diff-analysis",
        action="store_true",
        help="Enable differential analysis against baseline responses"
    )
    parser.add_argument(
        "--detect-reflection",
        action="store_true",
        help="Detect if payloads are reflected in responses (XSS testing)"
    )
    parser.add_argument(
        "--auto-throttle",
        action="store_true",
        help="Automatically detect rate limiting and adjust request rate"
    )
    parser.add_argument(
        "--waf-detect",
        action="store_true",
        help="Attempt to detect Web Application Firewall (WAF) presence"
    )

    # Misc
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    return parser


def validate_proxy(proxy_url: str) -> Dict[str, str]:
    """Validate and parse proxy URL.

    Args:
        proxy_url: Proxy URL string.

    Returns:
        Dictionary with 'http' and 'https' proxy settings.

    Raises:
        ConfigurationError: If proxy URL is invalid.
    """
    try:
        parsed_proxy = urlparse(proxy_url)
    except ValueError:
        raise ConfigurationError(f"Invalid proxy URL format: {proxy_url}")

    if not parsed_proxy.scheme or not parsed_proxy.netloc:
        raise ConfigurationError(f"Invalid proxy URL format: {proxy_url}")

    return {"http": proxy_url, "https": proxy_url}


def generate_tasks(
    base_requests_data: List[Dict[str, Any]],
    config
) -> tuple[List[TaskData], Dict[str, int]]:
    """Generate tasks from base requests and configuration rules.

    Args:
        base_requests_data: List of raw request dictionaries.
        config: Application configuration.

    Returns:
        Tuple of (task_list, statistics_dict).
    """
    tasks_to_run: List[TaskData] = []
    request_id_counter = 1
    stats = {
        'skipped_filter': 0,
        'skipped_target': 0,
        'total_potential': 0
    }

    rules_list = config.rules if hasattr(config, 'rules') else []
    modifications_active = bool(rules_list)

    for base_request_data in base_requests_data:
        try:
            base_components = prepare_request_components(base_request_data)
        except RequestParsingError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            continue

        if base_components is None:
            continue

        if modifications_active:
            # Apply rules with filters
            for rule in rules_list:
                target_config = rule.get('target')
                payload_config = rule.get('payloads')
                filter_config = rule.get('filter')

                if not target_config or not payload_config:
                    continue

                # Check if request matches filter
                if not request_matches_filter(base_components, filter_config):
                    # Count skipped due to filter
                    try:
                        payloads_for_rule_check = load_payloads(payload_config)
                        if payloads_for_rule_check:
                            stats['skipped_filter'] += len(payloads_for_rule_check)
                            stats['total_potential'] += len(payloads_for_rule_check)
                    except PayloadLoadError:
                        pass
                    continue

                # Load payloads and apply modifications
                try:
                    payloads_for_rule = load_payloads(payload_config)
                except PayloadLoadError as e:
                    console.print(f"[bold red]Error:[/bold red] {e}")
                    continue

                if not payloads_for_rule:
                    continue

                for payload in payloads_for_rule:
                    stats['total_potential'] += 1
                    modified_components, success = apply_modification(
                        base_components, target_config, payload
                    )

                    if success:
                        # Get conditions from the rule
                        rule_conditions = rule.get('conditions')

                        tasks_to_run.append(TaskData(
                            id=request_id_counter,
                            components=modified_components,
                            payload_str=payload,
                            conditions=rule_conditions,
                            base_components=base_components  # Store original for baseline matching
                        ))
                        request_id_counter += 1
                    else:
                        stats['skipped_target'] += 1
        else:
            # No modifications, just replay base request
            tasks_to_run.append(TaskData(
                id=request_id_counter,
                components=base_components,
                payload_str="-",
                base_components=base_components  # Same as components when no modifications
            ))
            request_id_counter += 1

    return tasks_to_run, stats


def execute_tasks(
    tasks: List[TaskData],
    config,
    proxies: Optional[Dict[str, str]],
    output_file: Optional[str] = None,
    baseline_mode: bool = False,
    baseline_file: str = "baselines.json",
    diff_analysis: bool = False,
    detect_reflection: bool = False,
    auto_throttle: bool = False,
    waf_detect: bool = False
) -> List[Dict[str, Any]]:
    """Execute HTTP request tasks with progress tracking.

    Args:
        tasks: List of TaskData to execute.
        config: Application configuration.
        proxies: Proxy configuration dict.
        output_file: Optional path to save results.
        baseline_mode: Whether to run in baseline capture mode.
        baseline_file: Path to baseline file.
        diff_analysis: Whether to enable differential analysis.
        detect_reflection: Whether to detect payload reflection.
        auto_throttle: Whether to enable automatic rate limiting detection.
        waf_detect: Whether to detect WAF presence.

    Returns:
        List of result dictionaries.
    """
    total_requests = len(tasks)

    # Phase 1: Initialize components
    from pathlib import Path
    from .models.baseline import BaselineStore
    from .core.diff_analyzer import DifferentialAnalyzer
    from .core.reflection_detector import ReflectionDetector
    from .core.rate_limiter import RateLimiter

    # Initialize baseline store
    baseline_store = None
    diff_analyzer_instance = None
    if baseline_mode or diff_analysis:
        baseline_store = BaselineStore()

        # Load existing baselines if doing diff analysis
        if diff_analysis and Path(baseline_file).exists():
            try:
                baseline_store = BaselineStore.load_from_file(baseline_file)
                console.print(f"[cyan]Loaded {len(baseline_store.baselines)} baselines from {baseline_file}[/cyan]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load baselines: {e}[/yellow]")
                baseline_store = BaselineStore()

        # Create diff analyzer if needed
        if diff_analysis and not baseline_mode:
            diff_analyzer_instance = DifferentialAnalyzer()

    # Initialize reflection detector
    reflection_detector_instance = None
    if detect_reflection:
        reflection_detector_instance = ReflectionDetector()

    # Initialize rate limiter
    rate_limiter_instance = None
    if auto_throttle or waf_detect:
        rate_limiter_instance = RateLimiter(base_delay=config.delay)

    # Print active Phase 1 features
    active_features = []
    if baseline_mode:
        active_features.append("Baseline Capture")
    if diff_analysis:
        active_features.append("Differential Analysis")
    if detect_reflection:
        active_features.append("Reflection Detection")
    if auto_throttle:
        active_features.append("Auto-Throttle")
    if waf_detect:
        active_features.append("WAF Detection")

    if active_features:
        console.print(f"[bold green]Phase 1 Features:[/bold green] {', '.join(active_features)}")

    console.print(f"[cyan]Preparing to send {total_requests} requests using {config.threads} threads...[/cyan]")

    # Create progress bar and results table
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed} of {task.total})"),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=console
    )

    task_id = progress.add_task("[green]Sending Requests", total=total_requests)
    results_table = create_results_table()
    render_group = Group(progress, results_table)

    # Threading coordination
    threads: List[threading.Thread] = []
    task_index = 0
    rich_lock = threading.Lock()
    results_collector: List[Dict[str, Any]] = []  # Collect results for export
    baseline_miss_counter = {'count': 0}  # Track missing baselines for diff analysis

    with Live(render_group, refresh_per_second=10, console=console, vertical_overflow="visible"):
        session = requests.Session()

        # Main execution loop
        while task_index < total_requests or any(t.is_alive() for t in threads):
            # Start new threads up to the limit
            while task_index < total_requests and (threading.active_count() - 1 < config.threads):
                task_data = tasks[task_index]

                thread = threading.Thread(
                    target=make_request_worker,
                    args=(
                        task_data.id,
                        task_data.components,
                        task_data.payload_str,
                        session,
                        config,
                        results_table,
                        progress,
                        task_id,
                        proxies,
                        rich_lock,
                        task_data.conditions,
                        results_collector,
                        baseline_store,
                        diff_analyzer_instance,
                        reflection_detector_instance,
                        rate_limiter_instance,
                        baseline_mode,
                        task_data.base_components,  # Pass base components for baseline matching
                        baseline_miss_counter  # Track missing baselines
                    ),
                    daemon=True
                )
                threads.append(thread)
                thread.start()
                task_index += 1

                if config.delay > 0:
                    time.sleep(config.delay)

            # Small sleep to prevent busy waiting
            time.sleep(0.05)

    console.print(f"[bold green]Completed {total_requests} requests.[/bold green]")

    # Save baselines if in baseline mode
    if baseline_mode and baseline_store:
        try:
            baseline_store.save_to_file(baseline_file)
            console.print(f"[bold green]Saved {len(baseline_store.baselines)} baselines to:[/bold green] {baseline_file}")
        except Exception as e:
            console.print(f"[bold red]Failed to save baselines:[/bold red] {e}")

    # Report baseline matching statistics for diff analysis
    if diff_analysis and not baseline_mode:
        if baseline_miss_counter['count'] > 0:
            console.print(f"[bold yellow]⚠️  Baseline Matching:[/bold yellow] {baseline_miss_counter['count']} request(s) had no matching baseline.")
            console.print(f"[yellow]   Tip: Run --baseline-mode first to capture baselines from original requests.[/yellow]")
        elif baseline_store:
            console.print(f"[bold green]✓ Baseline Matching:[/bold green] All requests matched to baselines successfully.")

    # Print rate limiter statistics if enabled
    if rate_limiter_instance:
        stats = rate_limiter_instance.get_statistics()
        if stats['detected']:
            console.print(f"[bold yellow]Rate Limiting:[/bold yellow] Detected {stats['detection_count']} times, "
                         f"current delay: {stats['current_delay']:.2f}s")

    # Export results if output file specified
    if output_file and results_collector:
        from .ui.exporter import export_results
        from pathlib import Path

        output_path = Path(output_file)
        # Determine format from extension
        extension = output_path.suffix.lower()
        if extension == '.json':
            format_type = 'json'
        elif extension == '.csv':
            format_type = 'csv'
        elif extension in ('.html', '.htm'):
            format_type = 'html'
        else:
            format_type = 'json'  # Default to JSON

        try:
            export_results(results_collector, str(output_path), format_type)
            console.print(f"[bold green]Results exported to:[/bold green] {output_path}")
        except Exception as e:
            console.print(f"[bold red]Failed to export results:[/bold red] {e}")

    return results_collector


def main() -> int:
    """Main execution function.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    try:
        # Load configuration
        config = load_config(args.config)
        config = merge_cli_args(config, args)

        # Setup proxy if specified
        proxies: Optional[Dict[str, str]] = None
        if config.proxy:
            proxies = validate_proxy(config.proxy)
            console.print(f"[cyan]Using proxy:[/cyan] {config.proxy}")

            # Warn about SSL verification with local proxy
            parsed_proxy = urlparse(config.proxy)
            if config.verify_ssl and parsed_proxy.hostname in ('127.0.0.1', 'localhost'):
                console.print("[bold yellow]Warning:[/bold yellow] Using local proxy with SSL verification. Consider '--no-verify'.")

        # Load requests
        base_requests_data = load_requests(args.input_file)

        # Generate tasks
        tasks, stats = generate_tasks(base_requests_data, config)

        # Display statistics
        if config.rules:
            console.print(f"[cyan]Found {len(config.rules)} modification rules. Filters and per-rule payloads active.[/cyan]")

            # Warn if running baseline mode with modifications
            if args.baseline_mode:
                console.print("[bold yellow]⚠️  Warning:[/bold yellow] Running --baseline-mode with modification rules.")
                console.print("[yellow]   Baselines will be captured from ORIGINAL (unmodified) requests.[/yellow]")
                console.print("[yellow]   This is correct if you want to establish baselines before fuzzing.[/yellow]")

            if stats['skipped_filter'] > 0:
                console.print(f"[yellow]Skipped {stats['skipped_filter']} request iterations due to request filters.[/yellow]")
            if stats['skipped_target'] > 0:
                console.print(f"[yellow]Skipped {stats['skipped_target']} request iterations where the specific rule target was not found.[/yellow]")
            console.print(f"[cyan]Total potential modifications considered: {stats['total_potential']}[/cyan]")
        elif args.config:
            console.print("[yellow]Warning:[/yellow] Config has no 'rules' list. Replaying base requests.")
        else:
            console.print("[cyan]Info:[/cyan] No config specified. Replaying base requests.")

        if not tasks:
            console.print("[bold red]Error:[/bold red] No requests generated to send.")
            return 1

        # Execute tasks with Phase 1 features
        execute_tasks(
            tasks,
            config,
            proxies,
            args.output,
            baseline_mode=args.baseline_mode,
            baseline_file=args.baseline_file,
            diff_analysis=args.diff_analysis,
            detect_reflection=args.detect_reflection,
            auto_throttle=args.auto_throttle,
            waf_detect=args.waf_detect
        )

        return 0

    except ConfigurationError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        return 1
    except RequestParsingError as e:
        console.print(f"[bold red]Request Parsing Error:[/bold red] {e}")
        return 1
    except AvadaKedavraError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrupted by user.[/bold yellow]")
        return 130
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
