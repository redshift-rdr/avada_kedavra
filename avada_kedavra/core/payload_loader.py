# -*- coding: utf-8 -*-
"""Payload loading from various sources."""

from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.console import Console

from ..utils.exceptions import PayloadLoadError

console = Console()


def load_payloads(payload_config: Dict[str, Any]) -> Optional[List[str]]:
    """Load payloads from configuration.

    Args:
        payload_config: Dictionary with 'type' and 'source' keys.

    Returns:
        List of payload strings, or None if loading fails.

    Raises:
        PayloadLoadError: If payload configuration is invalid or loading fails.
    """
    if not isinstance(payload_config, dict):
        raise PayloadLoadError("Invalid 'payloads' section in rule.")

    payload_type = payload_config.get('type', 'list')
    source = payload_config.get('source')

    if source is None:
        raise PayloadLoadError("'source' missing in payload configuration.")

    payloads: List[str] = []

    if payload_type == 'list':
        if not isinstance(source, list):
            raise PayloadLoadError("Payload source must be a list for type 'list'.")
        payloads = [str(p) for p in source]

    elif payload_type == 'file':
        if not isinstance(source, str):
            raise PayloadLoadError("Payload source must be a filename for type 'file'.")
        try:
            payload_path = Path(source)
            if not payload_path.is_file():
                raise PayloadLoadError(f"Payload file not found: {source}")

            with open(payload_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                payloads = [line.strip() for line in f if line.strip()]

        except PayloadLoadError:
            raise
        except Exception as e:
            raise PayloadLoadError(f"Failed to read payload file {source}: {e}")

    elif payload_type == 'single':
        payloads = [str(source)]

    else:
        raise PayloadLoadError(f"Unknown payload type: {payload_type}")

    if not payloads:
        console.print(f"[bold yellow]Warning:[/bold yellow] No payloads loaded for rule (type: {payload_type}, source: {source}).")

    return payloads
