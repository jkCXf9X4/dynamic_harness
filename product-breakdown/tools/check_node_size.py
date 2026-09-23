#!/usr/bin/env python3
"""Node-size checker for the product-breakdown structure (AD-009).

Every markdown file under ``product-breakdown/`` is a node:

- **Index node** — one per folder, ``README.md``. Navigational only.
  Target <=40 lines, hard cap 75.
- **Leaf node** — one concern. Target <=50 lines, hard cap 75, minimum ~10.

Nodes that exceed the cap (or fall under the leaf minimum) are violations.
Existing oversized nodes are grandfathered via ``node_size_allowlist.txt``
(one repo-relative path per line, ``#`` comments allowed) and refactored under
IMP-016; once that allow-list is empty, ``--strict`` is clean.

Usage::

    python3 product-breakdown/tools/check_node_size.py            # report
    python3 product-breakdown/tools/check_node_size.py --strict   # non-zero on violation
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BREAKDOWN = REPO_ROOT / "product-breakdown"
ALLOWLIST = Path(__file__).resolve().parent / "node_size_allowlist.txt"

INDEX_TARGET = 40
INDEX_CAP = 75
LEAF_TARGET = 50
LEAF_CAP = 75
LEAF_MIN = 10


def classify(path: Path) -> str:
    return "index" if path.name == "README.md" else "leaf"


def load_allowlist() -> set[str]:
    if not ALLOWLIST.exists():
        return set()
    return {
        line.strip()
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check product-breakdown node sizes.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when a non-grandfathered node violates its budget",
    )
    args = parser.parse_args(argv)

    allow = load_allowlist()
    violations: list[tuple[str, str, int]] = []
    grandfathered: list[tuple[str, str, int]] = []

    for path in sorted(BREAKDOWN.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        kind = classify(path)
        lines = len(path.read_text(encoding="utf-8").splitlines())
        cap = INDEX_CAP if kind == "index" else LEAF_CAP
        over = lines > cap or (kind == "leaf" and lines < LEAF_MIN)
        if over:
            (grandfathered if rel in allow else violations).append((rel, kind, lines))

    stale = sorted(allow - {rel for rel, _, _ in violations + grandfathered})

    for rel, kind, lines in sorted(grandfathered):
        print(f"[grandfathered] {rel} ({kind}, {lines} lines)")
    for rel, kind, lines in sorted(violations):
        cap = INDEX_CAP if kind == "index" else LEAF_CAP
        print(f"[VIOLATION]     {rel} ({kind}, {lines} lines > cap {cap})")
    for rel in stale:
        print(f"[stale]         {rel} listed in allow-list but no longer violates")

    print(
        f"\n{len(grandfathered)} grandfathered, {len(violations)} violation(s), "
        f"{len(stale)} stale allow-list entr{'y' if len(stale) == 1 else 'ies'}."
    )

    if args.strict and (violations or stale):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
