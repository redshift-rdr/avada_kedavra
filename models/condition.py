# -*- coding: utf-8 -*-
"""Data models for response conditions."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


class ConditionType(Enum):
    """Types of response conditions."""
    STRING_IN_BODY = "string_in_body"
    STRING_IN_HEADERS = "string_in_headers"
    REGEX_IN_BODY = "regex_in_body"
    REGEX_IN_HEADERS = "regex_in_headers"
    STATUS_CODE = "status_code"
    CONTENT_LENGTH_GT = "content_length_gt"
    CONTENT_LENGTH_LT = "content_length_lt"
    CONTENT_LENGTH_EQ = "content_length_eq"
    RESPONSE_TIME_GT = "response_time_gt"
    RESPONSE_TIME_LT = "response_time_lt"


@dataclass
class ResponseData:
    """Captured response data for condition checking."""
    status_code: Optional[int] = None
    headers: Dict[str, str] = None
    body: str = ""
    content_length: int = 0
    response_time: float = 0.0
    error: str = ""

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


@dataclass
class ConditionResult:
    """Result of a condition check."""
    matched: bool
    condition_type: str
    description: str
    value: Any = None
