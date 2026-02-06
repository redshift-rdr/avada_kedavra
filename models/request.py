# -*- coding: utf-8 -*-
"""Data models for HTTP request components."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Any


@dataclass
class RequestComponents:
    """Represents parsed and structured HTTP request components.

    This class holds all the necessary information to construct an HTTP request,
    including URL parameters, headers, cookies, and body data.
    """
    method: str
    base_url: str
    url_params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    body_type: Optional[Literal['json', 'form', 'raw', 'multipart']] = None
    parsed_body: Optional[Dict[str, Any]] = None
    raw_body: Optional[str] = None
    has_body_params: bool = False
    original_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            'method': self.method,
            'base_url': self.base_url,
            'url_params': self.url_params,
            'headers': self.headers,
            'cookies': self.cookies,
            'body_type': self.body_type,
            'parsed_body': self.parsed_body,
            'raw_body': self.raw_body,
            'has_body_params': self.has_body_params,
            'original_data': self.original_data
        }


@dataclass
class AppConfig:
    """Application configuration with defaults."""
    timeout: int = 10
    verify_ssl: bool = True
    allow_redirects: bool = True
    threads: int = 5
    delay: float = 0.0
    proxy: Optional[str] = None
    rules: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            'timeout': self.timeout,
            'verify_ssl': self.verify_ssl,
            'allow_redirects': self.allow_redirects,
            'threads': self.threads,
            'delay': self.delay,
            'proxy': self.proxy,
            'rules': self.rules
        }


@dataclass
class TaskData:
    """Represents a single request task to be executed."""
    id: int
    components: RequestComponents
    payload_str: str = "-"
    conditions: Optional[Dict[str, Any]] = None
