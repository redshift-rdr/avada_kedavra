#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backward compatibility wrapper for the refactored avada_kedavra tool.

This module maintains the original CLI interface while delegating to the
new modular implementation.

DEPRECATED: This file is maintained for backward compatibility only.
Please use: python -m avada_kedavra [args]
"""

import sys
import warnings

# Show deprecation warning
warnings.warn(
    "Direct execution of requester.py is deprecated. "
    "Please use 'python -m avada_kedavra' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import and run the main function from the new module
from avada_kedavra.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
