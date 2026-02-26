#!/usr/bin/env python3
"""Stub — delegates to intersense/scripts/content-hash.py.

This file is kept for backward compatibility. The canonical version
lives in the intersense plugin.
"""
import os
import sys
from pathlib import Path

# Find intersense plugin root
_INTERSENSE_CANDIDATES = [
    # Monorepo layout
    Path(__file__).resolve().parent.parent.parent / "intersense" / "scripts" / "content-hash.py",
    # Installed plugin (marketplace cache)
    *sorted(Path.home().glob(".claude/plugins/cache/*/intersense/*/scripts/content-hash.py"), reverse=True),
]

for candidate in _INTERSENSE_CANDIDATES:
    if candidate.exists():
        os.execv(sys.executable, [sys.executable, str(candidate)] + sys.argv[1:])

print("intersense plugin not found — run content-hash.py from intersense directly", file=sys.stderr)
sys.exit(2)
