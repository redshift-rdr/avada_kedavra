# -*- coding: utf-8 -*-
"""Reflection detection for identifying payload echoing in responses."""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ReflectionMatch:
    """Represents a detected payload reflection."""

    payload: str
    location: str  # 'body', 'headers', 'both'
    context: str  # Surrounding context where reflection was found
    encoded: bool  # Whether payload appears encoded
    encoding_type: Optional[str] = None  # 'html', 'url', 'base64', etc.


class ReflectionDetector:
    """Detects if payloads are reflected in HTTP responses."""

    # Common encoding patterns
    HTML_ENTITIES = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '&': '&amp;',
    }

    def __init__(self, min_payload_length: int = 3):
        """Initialize reflection detector.

        Args:
            min_payload_length: Minimum payload length to check for reflection (avoid false positives).
        """
        self.min_payload_length = min_payload_length

    def detect_reflection(
        self,
        payload: str,
        response_body: str,
        response_headers: dict
    ) -> Optional[ReflectionMatch]:
        """Detect if payload is reflected in response.

        Args:
            payload: The payload string to search for.
            response_body: HTTP response body.
            response_headers: HTTP response headers dict.

        Returns:
            ReflectionMatch if reflection found, None otherwise.
        """
        if len(payload) < self.min_payload_length:
            return None

        # Check for exact match first
        found_in_body = payload in response_body
        found_in_headers = self._check_headers(payload, response_headers)

        if found_in_body or found_in_headers:
            location = self._determine_location(found_in_body, found_in_headers)
            context = self._extract_context(payload, response_body, found_in_body)
            return ReflectionMatch(
                payload=payload,
                location=location,
                context=context,
                encoded=False
            )

        # Check for encoded versions
        encoded_match = self._check_encoded_reflection(payload, response_body, response_headers)
        if encoded_match:
            return encoded_match

        return None

    def _check_headers(self, payload: str, headers: dict) -> bool:
        """Check if payload appears in response headers.

        Args:
            payload: Payload to search for.
            headers: Response headers dict.

        Returns:
            True if found in headers.
        """
        headers_str = str(headers).lower()
        return payload.lower() in headers_str

    def _determine_location(self, in_body: bool, in_headers: bool) -> str:
        """Determine where reflection was found.

        Args:
            in_body: Found in body.
            in_headers: Found in headers.

        Returns:
            Location string.
        """
        if in_body and in_headers:
            return "both"
        elif in_body:
            return "body"
        else:
            return "headers"

    def _extract_context(self, payload: str, response_body: str, in_body: bool) -> str:
        """Extract surrounding context where payload was reflected.

        Args:
            payload: The payload.
            response_body: Response body.
            in_body: Whether payload was found in body.

        Returns:
            Context string (truncated).
        """
        if not in_body:
            return "In headers"

        try:
            # Find position of payload
            pos = response_body.lower().find(payload.lower())
            if pos == -1:
                return "Found in body"

            # Extract 30 chars before and after
            start = max(0, pos - 30)
            end = min(len(response_body), pos + len(payload) + 30)
            context = response_body[start:end]

            # Clean up and truncate
            context = context.replace('\n', ' ').replace('\r', ' ')
            if len(context) > 80:
                context = context[:77] + "..."

            return context
        except Exception:
            return "Found in body"

    def _check_encoded_reflection(
        self,
        payload: str,
        response_body: str,
        response_headers: dict
    ) -> Optional[ReflectionMatch]:
        """Check for encoded versions of payload.

        Args:
            payload: Original payload.
            response_body: Response body.
            response_headers: Response headers.

        Returns:
            ReflectionMatch if encoded version found.
        """
        # HTML entity encoding
        html_encoded = self._html_encode(payload)
        if html_encoded != payload and html_encoded in response_body:
            context = self._extract_context(html_encoded, response_body, True)
            return ReflectionMatch(
                payload=payload,
                location="body",
                context=context,
                encoded=True,
                encoding_type="html"
            )

        # URL encoding
        url_encoded = self._url_encode(payload)
        if url_encoded != payload and url_encoded in response_body:
            context = self._extract_context(url_encoded, response_body, True)
            return ReflectionMatch(
                payload=payload,
                location="body",
                context=context,
                encoded=True,
                encoding_type="url"
            )

        # JavaScript escape sequences
        js_escaped = self._js_escape(payload)
        if js_escaped != payload and js_escaped in response_body:
            context = self._extract_context(js_escaped, response_body, True)
            return ReflectionMatch(
                payload=payload,
                location="body",
                context=context,
                encoded=True,
                encoding_type="javascript"
            )

        return None

    def _html_encode(self, text: str) -> str:
        """HTML entity encode special characters.

        Args:
            text: Input text.

        Returns:
            HTML encoded text.
        """
        result = text
        for char, entity in self.HTML_ENTITIES.items():
            result = result.replace(char, entity)
        return result

    def _url_encode(self, text: str) -> str:
        """URL encode text.

        Args:
            text: Input text.

        Returns:
            URL encoded text.
        """
        from urllib.parse import quote
        return quote(text, safe='')

    def _js_escape(self, text: str) -> str:
        """JavaScript escape text.

        Args:
            text: Input text.

        Returns:
            JavaScript escaped text.
        """
        # Common JS escapes
        result = text.replace('\\', '\\\\')
        result = result.replace('"', '\\"')
        result = result.replace("'", "\\'")
        result = result.replace('<', '\\x3c')
        result = result.replace('>', '\\x3e')
        return result

    def format_reflection_result(self, match: ReflectionMatch) -> str:
        """Format reflection match for display.

        Args:
            match: ReflectionMatch object.

        Returns:
            Formatted string.
        """
        encoding_info = f" [{match.encoding_type}]" if match.encoded else ""
        return f"Reflected({match.location}){encoding_info}"
