# -*- coding: utf-8 -*-
"""Configuration loading and management."""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console

from ..models.request import AppConfig
from ..models.auth import parse_auth_config
from ..utils.exceptions import ConfigurationError

console = Console()


def load_config(filepath: Optional[str]) -> AppConfig:
    """Load configuration from YAML file.

    Args:
        filepath: Path to the YAML configuration file. If None, returns default config.

    Returns:
        AppConfig object with loaded configuration.

    Raises:
        ConfigurationError: If file not found, invalid YAML, or invalid structure.
    """
    if not filepath:
        return AppConfig()

    try:
        config_path = Path(filepath)
        if not config_path.exists():
            raise ConfigurationError(f"Config file not found: {filepath}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not isinstance(config_data, dict):
            raise ConfigurationError(f"Config file {filepath} must contain a dictionary.")

        if 'rules' in config_data and not isinstance(config_data.get('rules'), list):
            raise ConfigurationError("'rules' key in config must be a list.")

        # Parse auth config if present
        auth_config = None
        if 'auth' in config_data and isinstance(config_data['auth'], dict):
            try:
                auth_config = parse_auth_config(config_data['auth'])
            except ValueError as e:
                raise ConfigurationError(f"Invalid auth configuration: {e}")

        # Build AppConfig from loaded data
        return AppConfig(
            timeout=config_data.get('timeout', 10),
            verify_ssl=config_data.get('verify_ssl', True),
            allow_redirects=config_data.get('allow_redirects', True),
            threads=config_data.get('threads', 5),
            delay=config_data.get('delay', 0.0),
            proxy=config_data.get('proxy'),
            rules=config_data.get('rules', []),
            auth=auth_config,
            continue_on_auth_errors=config_data.get('continue_on_auth_errors', False)
        )

    except FileNotFoundError:
        raise ConfigurationError(f"Config file not found: {filepath}")
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {filepath}: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load config: {e}")


def merge_cli_args(config: AppConfig, args) -> AppConfig:
    """Merge command-line arguments into configuration.

    Args:
        config: Base configuration from file.
        args: Parsed command-line arguments.

    Returns:
        Updated AppConfig with CLI overrides applied.
    """
    # Override with CLI arguments if provided
    if args.timeout is not None:
        config.timeout = args.timeout
    if args.no_verify:
        config.verify_ssl = False
    if args.no_redirects:
        config.allow_redirects = False
    if hasattr(args, 'threads') and args.threads:
        config.threads = args.threads
    if hasattr(args, 'delay') and args.delay is not None:
        config.delay = args.delay
    if hasattr(args, 'proxy') and args.proxy:
        config.proxy = args.proxy
    if hasattr(args, 'continue_on_auth_errors') and args.continue_on_auth_errors:
        config.continue_on_auth_errors = True
    if hasattr(args, 'no_live') and args.no_live:
        config.no_live = True

    return config
