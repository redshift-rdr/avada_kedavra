# -*- coding: utf-8 -*-
"""Baseline data models for differential analysis."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import hashlib
import json


@dataclass
class BaselineResponse:
    """Represents a baseline response for comparison."""

    request_id: str  # Hash of request components (method + url + body)
    status_code: int
    content_length: int
    response_time: float
    body: str
    headers: Dict[str, str]
    body_hash: str = ""

    def __post_init__(self):
        """Calculate body hash after initialization."""
        if not self.body_hash:
            self.body_hash = hashlib.sha256(self.body.encode('utf-8', errors='ignore')).hexdigest()


@dataclass
class DiffResult:
    """Represents the difference between baseline and fuzzed response."""

    has_difference: bool
    similarity_ratio: float  # 0.0 to 1.0, where 1.0 is identical
    status_code_diff: bool
    size_diff_bytes: int
    size_diff_percent: float
    time_diff_seconds: float
    time_diff_percent: float
    body_changed: bool
    headers_changed: bool

    # Anomaly flags
    is_size_anomaly: bool = False
    is_time_anomaly: bool = False
    is_error_introduced: bool = False

    # Details
    new_errors: list = field(default_factory=list)
    diff_summary: str = ""


@dataclass
class BaselineStore:
    """Stores baseline responses for comparison."""

    baselines: Dict[str, BaselineResponse] = field(default_factory=dict)

    def add_baseline(self, baseline: BaselineResponse) -> None:
        """Add or update a baseline response."""
        self.baselines[baseline.request_id] = baseline

    def get_baseline(self, request_id: str) -> Optional[BaselineResponse]:
        """Retrieve a baseline response by request ID."""
        return self.baselines.get(request_id)

    def has_baseline(self, request_id: str) -> bool:
        """Check if baseline exists for request ID."""
        return request_id in self.baselines

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'baselines': {
                req_id: {
                    'request_id': b.request_id,
                    'status_code': b.status_code,
                    'content_length': b.content_length,
                    'response_time': b.response_time,
                    'body': b.body,
                    'headers': b.headers,
                    'body_hash': b.body_hash
                }
                for req_id, b in self.baselines.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaselineStore':
        """Load from dictionary."""
        store = cls()
        for req_id, b_data in data.get('baselines', {}).items():
            baseline = BaselineResponse(
                request_id=b_data['request_id'],
                status_code=b_data['status_code'],
                content_length=b_data['content_length'],
                response_time=b_data['response_time'],
                body=b_data['body'],
                headers=b_data['headers'],
                body_hash=b_data['body_hash']
            )
            store.add_baseline(baseline)
        return store

    def save_to_file(self, filepath: str) -> None:
        """Save baselines to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> 'BaselineStore':
        """Load baselines from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
