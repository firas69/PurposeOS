"""
conftest.py — Shared pytest fixtures for the PurposeOS test suite.
Lives at the project root alongside the test files.
"""
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `import purposeos` resolves
# to the local source tree, not any installed copy.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
