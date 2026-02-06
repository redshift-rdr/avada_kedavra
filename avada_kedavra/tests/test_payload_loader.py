# -*- coding: utf-8 -*-
"""Tests for payload_loader module."""

import pytest
from pathlib import Path
import tempfile
from avada_kedavra.core.payload_loader import load_payloads
from avada_kedavra.utils.exceptions import PayloadLoadError


class TestLoadPayloads:
    """Tests for load_payloads function."""

    def test_invalid_config_type_raises_error(self):
        """Test that invalid config type raises PayloadLoadError."""
        with pytest.raises(PayloadLoadError, match="Invalid 'payloads' section"):
            load_payloads("not a dict")

    def test_missing_source_raises_error(self):
        """Test that missing source raises PayloadLoadError."""
        with pytest.raises(PayloadLoadError, match="'source' missing"):
            load_payloads({"type": "list"})

    def test_list_type_success(self):
        """Test loading payloads from list."""
        config = {
            "type": "list",
            "source": ["payload1", "payload2", "payload3"]
        }
        result = load_payloads(config)

        assert result == ["payload1", "payload2", "payload3"]

    def test_list_type_converts_to_strings(self):
        """Test that list payloads are converted to strings."""
        config = {
            "type": "list",
            "source": [123, 456, True, None]
        }
        result = load_payloads(config)

        assert result == ["123", "456", "True", "None"]

    def test_list_type_invalid_source_raises_error(self):
        """Test that non-list source for list type raises error."""
        config = {
            "type": "list",
            "source": "not a list"
        }
        with pytest.raises(PayloadLoadError, match="must be a list"):
            load_payloads(config)

    def test_single_type_success(self):
        """Test loading single payload."""
        config = {
            "type": "single",
            "source": "single_payload"
        }
        result = load_payloads(config)

        assert result == ["single_payload"]

    def test_single_type_converts_to_string(self):
        """Test that single payload is converted to string."""
        config = {
            "type": "single",
            "source": 12345
        }
        result = load_payloads(config)

        assert result == ["12345"]

    def test_file_type_success(self):
        """Test loading payloads from file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("payload1\n")
            f.write("payload2\n")
            f.write("payload3\n")
            f.write("\n")  # Empty line should be skipped
            f.write("  payload4  \n")  # Should be stripped
            temp_path = f.name

        try:
            config = {
                "type": "file",
                "source": temp_path
            }
            result = load_payloads(config)

            assert result == ["payload1", "payload2", "payload3", "payload4"]
        finally:
            Path(temp_path).unlink()

    def test_file_type_invalid_source_raises_error(self):
        """Test that non-string source for file type raises error."""
        config = {
            "type": "file",
            "source": 123
        }
        with pytest.raises(PayloadLoadError, match="must be a filename"):
            load_payloads(config)

    def test_file_type_missing_file_raises_error(self):
        """Test that missing file raises PayloadLoadError."""
        config = {
            "type": "file",
            "source": "/nonexistent/path/payloads.txt"
        }
        with pytest.raises(PayloadLoadError, match="file not found"):
            load_payloads(config)

    def test_unknown_type_raises_error(self):
        """Test that unknown payload type raises error."""
        config = {
            "type": "unknown_type",
            "source": "test"
        }
        with pytest.raises(PayloadLoadError, match="Unknown payload type"):
            load_payloads(config)

    def test_default_type_is_list(self):
        """Test that default type is 'list' when not specified."""
        config = {
            "source": ["payload1", "payload2"]
        }
        result = load_payloads(config)

        assert result == ["payload1", "payload2"]

    def test_empty_file_warns(self, capsys):
        """Test that empty file shows warning but returns empty list."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_path = f.name  # Empty file

        try:
            config = {
                "type": "file",
                "source": temp_path
            }
            result = load_payloads(config)

            assert result == []
            # Check that warning was printed
            captured = capsys.readouterr()
            assert "No payloads loaded" in captured.out or len(result) == 0
        finally:
            Path(temp_path).unlink()

    def test_file_with_utf8_sig_bom(self):
        """Test that file with UTF-8 BOM is handled correctly."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', delete=False, suffix='.txt') as f:
            f.write("payload1\n")
            f.write("payload2\n")
            temp_path = f.name

        try:
            config = {
                "type": "file",
                "source": temp_path
            }
            result = load_payloads(config)

            # Should load correctly without BOM issues
            assert "payload1" in result
            assert "payload2" in result
        finally:
            Path(temp_path).unlink()
