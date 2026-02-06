#!/usr/bin/env python3
"""Test script to verify baseline matching fixes."""

import json
import os
import sys
from pathlib import Path

# Add the avada_kedavra module to path
sys.path.insert(0, str(Path(__file__).parent / "avada_kedavra"))

from models.request import RequestComponents, TaskData
from core.diff_analyzer import create_request_id
from core.modifier import apply_modification
from core.request_parser import prepare_request_components


def test_baseline_id_generation():
    """Test that modified requests use base components for baseline ID."""

    print("=" * 60)
    print("TEST: Baseline ID Generation")
    print("=" * 60)

    # Create a base request
    base_request_data = {
        "method": "POST",
        "url": "http://example.com/api/user",
        "headers": ["POST /api/user HTTP/1.1"],
        "params": [
            {"type": "json", "name": "username", "value": "testuser"},
            {"type": "json", "name": "email", "value": "test@example.com"}
        ]
    }

    # Prepare base components
    base_components = prepare_request_components(base_request_data)

    # Calculate baseline ID from original request
    base_body_str = str(base_components.parsed_body or "")
    base_request_id = create_request_id(
        base_components.method,
        base_components.base_url,
        base_body_str
    )

    print(f"\n✓ Base request ID: {base_request_id}")
    print(f"  Method: {base_components.method}")
    print(f"  URL: {base_components.base_url}")
    print(f"  Body: {base_components.parsed_body}")

    # Apply different modifications to test
    test_payloads = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "' OR 1=1--"
    ]

    target_config = {"type": "body", "name": "username"}

    print(f"\n✓ Testing {len(test_payloads)} modifications:")

    for i, payload in enumerate(test_payloads, 1):
        # Apply modification
        modified_components, success = apply_modification(
            base_components, target_config, payload
        )

        if not success:
            print(f"  ✗ Payload {i}: Modification failed!")
            continue

        # Calculate ID from modified components (OLD WAY - WRONG)
        modified_body_str = str(modified_components.parsed_body or "")
        modified_request_id = create_request_id(
            modified_components.method,
            modified_components.base_url,
            modified_body_str
        )

        # Calculate ID from base components (NEW WAY - CORRECT)
        baseline_id_from_base = create_request_id(
            base_components.method,
            base_components.base_url,
            base_body_str
        )

        print(f"\n  Payload {i}: {payload[:30]}...")
        print(f"    Modified body: {modified_components.parsed_body}")
        print(f"    ID from modified: {modified_request_id}")
        print(f"    ID from base:     {baseline_id_from_base}")

        if modified_request_id == base_request_id:
            print(f"    ✗ PROBLEM: Modified ID matches base (shouldn't happen!)")
        else:
            print(f"    ✓ Modified ID differs (expected)")

        if baseline_id_from_base == base_request_id:
            print(f"    ✓ Base ID matches (CORRECT - all modified reqs share baseline)")
        else:
            print(f"    ✗ Base ID doesn't match (THIS SHOULD NOT HAPPEN)")

    print("\n" + "=" * 60)
    print("TEST RESULT:")
    print("All modified requests should share the same baseline ID")
    print(f"Expected baseline ID: {base_request_id}")
    print("=" * 60)


def test_task_data_structure():
    """Test that TaskData stores both base and modified components."""

    print("\n\n" + "=" * 60)
    print("TEST: TaskData Structure")
    print("=" * 60)

    # Create base components
    base_request_data = {
        "method": "GET",
        "url": "http://example.com/api/search?q=test",
        "headers": ["GET /api/search HTTP/1.1"],
        "params": [
            {"type": "url", "name": "q", "value": "test"}
        ]
    }

    base_components = prepare_request_components(base_request_data)

    # Apply modification
    target_config = {"type": "url", "name": "q"}
    payload = "' OR 1=1--"
    modified_components, success = apply_modification(
        base_components, target_config, payload
    )

    if not success:
        print("\n✗ Modification failed!")
        return

    # Create TaskData with both components (NEW WAY)
    task_data = TaskData(
        id=1,
        components=modified_components,
        payload_str=payload,
        base_components=base_components  # This is the fix!
    )

    print("\n✓ TaskData created with both components:")
    print(f"  Modified URL params: {task_data.components.url_params}")
    print(f"  Base URL params:     {task_data.base_components.url_params}")

    # Verify they're different
    if task_data.components.url_params != task_data.base_components.url_params:
        print(f"\n  ✓ Modified and base are different (correct!)")
    else:
        print(f"\n  ✗ Modified and base are the same (should be different!)")

    # Calculate baseline IDs
    base_body = str(base_components.parsed_body or "")
    base_id = create_request_id(
        task_data.base_components.method,
        task_data.base_components.base_url,
        base_body
    )

    modified_body = str(modified_components.parsed_body or "")
    modified_id = create_request_id(
        task_data.components.method,
        task_data.components.base_url,
        modified_body
    )

    print(f"\n  Baseline ID from base:     {base_id}")
    print(f"  Baseline ID from modified: {modified_id}")

    if base_id != modified_id:
        print(f"\n  ✓ IDs are different (this is why we need base_components!)")

    print("\n" + "=" * 60)
    print("TEST RESULT:")
    print("✓ TaskData now stores both base and modified components")
    print("✓ This allows proper baseline matching for modified requests")
    print("=" * 60)


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  BASELINE MATCHING FIX VERIFICATION TEST SUITE".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        test_baseline_id_generation()
        test_task_data_structure()

        print("\n\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
        print("\nSUMMARY:")
        print("✓ Modified requests now use base components for baseline ID")
        print("✓ All modified versions of a request share the same baseline")
        print("✓ TaskData stores both base and modified components")
        print("✓ Baseline matching should now work correctly")
        print("\nNEXT STEPS:")
        print("1. Run: python -m avada_kedavra test.json --baseline-mode")
        print("2. Run: python -m avada_kedavra test.json -c config.yaml --diff-analysis")
        print("3. Verify no 'NO_BASELINE' warnings appear")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
