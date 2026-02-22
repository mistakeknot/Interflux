#!/usr/bin/env python3
"""Compute a deterministic SHA-256 content hash from a project's key files.

Used by flux-drive to detect cache staleness for domain detection results.
Hashes README, build files, and up to 3 key source files in deterministic
order, producing a stable fingerprint that changes when project structure
or content changes.

Exit codes:
    0  Hash computed (or --check matched)
    1  No hashable files found (or --check mismatched)
    2  Fatal error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# README variants, checked in priority order
README_NAMES = ("README.md", "README.rst", "README.txt", "README")

# Build/config files to include when present
BUILD_FILES = (
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pyproject.toml",
    "build.gradle",
    "pom.xml",
    "Makefile",
    "CMakeLists.txt",
)

# Source directories to scan for key source files
SOURCE_DIRS = ("src", "lib")

# Source extensions eligible for key-file selection
SOURCE_EXTENSIONS = frozenset({
    ".py", ".go", ".rs", ".ts", ".js", ".jsx", ".tsx",
    ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp",
    ".rb", ".cs", ".dart", ".gd", ".lua", ".zig",
})

# Max source files to include
MAX_SOURCE_FILES = 3

# Max file size before treating as binary (1 MB)
MAX_FILE_SIZE = 1_048_576

# Bytes to sample for binary detection
BINARY_CHECK_SIZE = 512


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _is_binary(path: Path) -> bool:
    """Check if a file is likely binary.

    A file is considered binary if it exceeds MAX_FILE_SIZE or contains
    null bytes in the first BINARY_CHECK_SIZE bytes.
    """
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return True
        with open(path, "rb") as f:
            chunk = f.read(BINARY_CHECK_SIZE)
        return b"\x00" in chunk
    except OSError:
        return True


def _find_readme(project: Path) -> Path | None:
    """Find the first existing README variant."""
    for name in README_NAMES:
        candidate = project / name
        if candidate.is_file() and not _is_binary(candidate):
            return candidate
    return None


def _find_build_files(project: Path) -> list[Path]:
    """Find existing build/config files in the project root."""
    found: list[Path] = []
    for name in BUILD_FILES:
        candidate = project / name
        if candidate.is_file() and not _is_binary(candidate):
            found.append(candidate)
    return found


def _find_key_source_files(project: Path) -> list[Path]:
    """Find up to MAX_SOURCE_FILES key source files.

    Scans SOURCE_DIRS (and the project root as fallback), picks the most
    common source extension, then returns the first MAX_SOURCE_FILES files
    of that extension sorted by relative path.
    """
    candidates: list[Path] = []

    # Collect from source directories first
    for dirname in SOURCE_DIRS:
        source_dir = project / dirname
        if source_dir.is_dir():
            try:
                for entry in source_dir.rglob("*"):
                    if (
                        entry.is_file()
                        and entry.suffix in SOURCE_EXTENSIONS
                        and not _is_binary(entry)
                    ):
                        candidates.append(entry)
            except OSError:
                pass

    # Fallback: scan project root (non-recursively)
    if not candidates:
        try:
            for entry in project.iterdir():
                if (
                    entry.is_file()
                    and entry.suffix in SOURCE_EXTENSIONS
                    and not _is_binary(entry)
                ):
                    candidates.append(entry)
        except OSError:
            pass

    if not candidates:
        return []

    # Find the most common extension
    ext_counts: Counter[str] = Counter(c.suffix for c in candidates)
    dominant_ext = ext_counts.most_common(1)[0][0]

    # Filter to dominant extension, sort by relative path
    filtered = sorted(
        (c for c in candidates if c.suffix == dominant_ext),
        key=lambda p: str(p.relative_to(project)),
    )
    return filtered[:MAX_SOURCE_FILES]


def discover_files(project: Path) -> list[Path]:
    """Discover all hashable files in deterministic order.

    Returns absolute paths sorted by their relative path from project root.
    """
    files: list[Path] = []

    readme = _find_readme(project)
    if readme is not None:
        files.append(readme)

    files.extend(_find_build_files(project))
    files.extend(_find_key_source_files(project))

    # Deduplicate (a root .py file might appear from both build and source)
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)

    # Sort by relative path for determinism
    unique.sort(key=lambda p: str(p.relative_to(project)))
    return unique


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def compute_hash(project: Path, files: list[Path]) -> str:
    """Compute SHA-256 hash from file paths and contents.

    File contents are concatenated with null-byte separators:
        <relative_path>\\0<content>\\0<relative_path>\\0<content>...

    Returns 'sha256:<hex>' string.
    """
    h = hashlib.sha256()
    for i, filepath in enumerate(files):
        rel_path = str(filepath.relative_to(project))
        try:
            content = filepath.read_bytes()
        except OSError:
            continue
        if i > 0:
            h.update(b"\x00")
        h.update(rel_path.encode("utf-8"))
        h.update(b"\x00")
        h.update(content)
    return f"sha256:{h.hexdigest()}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute deterministic SHA-256 content hash from project key files.",
    )
    parser.add_argument("project_root", type=Path, help="Path to the project root")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON with hash and file list",
    )
    parser.add_argument(
        "--check",
        type=str,
        default=None,
        metavar="HASH",
        help="Compare computed hash against provided hash",
    )
    args = parser.parse_args()

    project = args.project_root.resolve()
    if not project.is_dir():
        print(f"Error: {project} is not a directory", file=sys.stderr)
        return 2

    try:
        files = discover_files(project)
    except Exception as exc:
        print(f"Error discovering files: {exc}", file=sys.stderr)
        return 2

    if not files:
        if args.json_output:
            print(json.dumps({"error": "no hashable files found", "files": []}))
        else:
            print("Error: no hashable files found", file=sys.stderr)
        return 1

    try:
        rel_paths = [str(f.relative_to(project)) for f in files]
        content_hash = compute_hash(project, files)
    except Exception as exc:
        print(f"Error computing hash: {exc}", file=sys.stderr)
        return 2

    # --check mode
    if args.check is not None:
        if content_hash == args.check:
            if args.json_output:
                print(json.dumps({"match": True, "hash": content_hash, "files": rel_paths}))
            return 0
        else:
            if args.json_output:
                print(json.dumps({"match": False, "expected": args.check, "actual": content_hash, "files": rel_paths}))
            else:
                print(f"Mismatch: expected {args.check}, got {content_hash}", file=sys.stderr)
            return 1

    # Normal output
    if args.json_output:
        print(json.dumps({"hash": content_hash, "files": rel_paths}))
    else:
        print(content_hash)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
