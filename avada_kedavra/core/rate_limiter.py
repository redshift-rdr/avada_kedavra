# -*- coding: utf-8 -*-
"""Adaptive rate limiting and WAF detection."""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional, List
from collections import deque


@dataclass
class RateLimitEvent:
    """Represents a rate limit event."""

    timestamp: float
    status_code: int
    response_body: str = ""


@dataclass
class RateLimitState:
    """Tracks rate limiting state."""

    enabled: bool = True
    detected: bool = False
    detection_count: int = 0
    last_detection_time: Optional[float] = None

    # Adaptive throttling
    current_delay: float = 0.0
    base_delay: float = 0.0

    # Event tracking
    recent_events: deque = field(default_factory=lambda: deque(maxlen=50))

    # Lock for thread safety
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimiter:
    """Adaptive rate limiter with WAF detection."""

    # Common rate limit indicators
    RATE_LIMIT_STATUS_CODES = [429, 503]

    RATE_LIMIT_KEYWORDS = [
        'rate limit',
        'too many requests',
        'throttle',
        'quota exceeded',
        'slow down',
        'try again later',
        'request limit',
    ]

    # WAF detection patterns
    WAF_PATTERNS = [
        'cloudflare',
        'akamai',
        'imperva',
        'f5',
        'modsecurity',
        'aws waf',
        'barracuda',
        'sucuri',
        'wordfence',
        'blocked',
        'forbidden',
        'access denied',
    ]

    def __init__(
        self,
        base_delay: float = 0.0,
        max_delay: float = 5.0,
        backoff_multiplier: float = 1.5,
        cooldown_time: float = 30.0
    ):
        """Initialize rate limiter.

        Args:
            base_delay: Base delay between requests (seconds).
            max_delay: Maximum delay to apply (seconds).
            backoff_multiplier: Multiplier for adaptive backoff.
            cooldown_time: Time to wait before reducing delay after detection (seconds).
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.cooldown_time = cooldown_time

        self.state = RateLimitState(base_delay=base_delay)

    def check_response(
        self,
        status_code: int,
        response_body: str = "",
        response_headers: dict = None
    ) -> bool:
        """Check if response indicates rate limiting.

        Args:
            status_code: HTTP status code.
            response_body: Response body text.
            response_headers: Response headers dict.

        Returns:
            True if rate limiting detected.
        """
        if not self.state.enabled:
            return False

        is_rate_limited = False

        # Check status code
        if status_code in self.RATE_LIMIT_STATUS_CODES:
            is_rate_limited = True

        # Check response body for keywords
        if not is_rate_limited and response_body:
            body_lower = response_body.lower()
            for keyword in self.RATE_LIMIT_KEYWORDS:
                if keyword in body_lower:
                    is_rate_limited = True
                    break

        # Check for Retry-After header
        if not is_rate_limited and response_headers:
            if 'Retry-After' in response_headers or 'retry-after' in response_headers:
                is_rate_limited = True

        if is_rate_limited:
            self._handle_rate_limit_detection(status_code, response_body)

        return is_rate_limited

    def detect_waf(self, response_body: str, response_headers: dict = None) -> Optional[str]:
        """Detect if a WAF is present based on response.

        Args:
            response_body: Response body text.
            response_headers: Response headers dict.

        Returns:
            WAF name if detected, None otherwise.
        """
        body_lower = response_body.lower()

        # Check body for WAF patterns
        for pattern in self.WAF_PATTERNS:
            if pattern in body_lower:
                return pattern.upper()

        # Check headers for WAF signatures
        if response_headers:
            headers_str = str(response_headers).lower()
            for pattern in self.WAF_PATTERNS:
                if pattern in headers_str:
                    return pattern.upper()

        return None

    def _handle_rate_limit_detection(self, status_code: int, response_body: str) -> None:
        """Handle rate limit detection and adjust throttling.

        Args:
            status_code: HTTP status code.
            response_body: Response body.
        """
        with self.state.lock:
            self.state.detected = True
            self.state.detection_count += 1
            self.state.last_detection_time = time.time()

            # Record event
            event = RateLimitEvent(
                timestamp=time.time(),
                status_code=status_code,
                response_body=response_body[:200]  # Truncate for storage
            )
            self.state.recent_events.append(event)

            # Increase delay adaptively
            if self.state.current_delay == 0:
                self.state.current_delay = max(0.5, self.base_delay)
            else:
                self.state.current_delay = min(
                    self.state.current_delay * self.backoff_multiplier,
                    self.max_delay
                )

    def get_delay(self) -> float:
        """Get the current delay to apply.

        Returns:
            Delay in seconds.
        """
        with self.state.lock:
            # Check if we should reduce delay (cooldown period passed)
            if self.state.detected and self.state.last_detection_time:
                time_since_detection = time.time() - self.state.last_detection_time

                if time_since_detection > self.cooldown_time:
                    # Gradually reduce delay
                    self.state.current_delay = max(
                        self.base_delay,
                        self.state.current_delay / self.backoff_multiplier
                    )

                    # Reset if back to base
                    if self.state.current_delay <= self.base_delay:
                        self.state.detected = False

            return self.state.current_delay

    def apply_delay(self) -> None:
        """Apply the current delay (sleep)."""
        delay = self.get_delay()
        if delay > 0:
            time.sleep(delay)

    def get_statistics(self) -> dict:
        """Get rate limiting statistics.

        Returns:
            Dictionary with statistics.
        """
        with self.state.lock:
            return {
                'enabled': self.state.enabled,
                'detected': self.state.detected,
                'detection_count': self.state.detection_count,
                'current_delay': self.state.current_delay,
                'base_delay': self.base_delay,
                'recent_events_count': len(self.state.recent_events)
            }

    def reset(self) -> None:
        """Reset rate limiter state."""
        with self.state.lock:
            self.state.detected = False
            self.state.detection_count = 0
            self.state.last_detection_time = None
            self.state.current_delay = self.base_delay
            self.state.recent_events.clear()

    def disable(self) -> None:
        """Disable rate limiting detection."""
        with self.state.lock:
            self.state.enabled = False

    def enable(self) -> None:
        """Enable rate limiting detection."""
        with self.state.lock:
            self.state.enabled = True
