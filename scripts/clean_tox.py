#!/usr/bin/env python3
"""Purge stale tox build artefacts to reclaim disk space.

Usage:
    python scripts/clean_tox.py          # purge temp packages only
    python scripts/clean_tox.py --full   # wipe .tox entirely (next tox run rebuilds)

What gets cleaned:
    --default:  .tox/.tmp/package/  (old sdist builds, typically 0.5-5 MB)
    --full:     entire .tox/        (venvs + caches, typically 1-5 GB)
"""

import argparse
import shutil
import sys
from pathlib import Path


def _sizeof_fmt(num: float) -> str:
    """Convert bytes to human-readable size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory recursively."""
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def purge_tmp_packages(tox_dir: Path) -> None:
    """Remove .tox/.tmp/package/ build artefacts."""
    tmp_pkg = tox_dir / ".tmp" / "package"
    if not tmp_pkg.exists():
        print("  Nothing to clean: .tox/.tmp/package/ does not exist.")
        return

    size = _dir_size(tmp_pkg)
    count = len(list(tmp_pkg.iterdir()))
    shutil.rmtree(tmp_pkg)
    print(f"  Purged {count} build(s) from .tox/.tmp/package/ ({_sizeof_fmt(size)})")


def purge_full(tox_dir: Path) -> None:
    """Remove entire .tox directory. Next tox run rebuilds from scratch."""
    if not tox_dir.exists():
        print("  Nothing to clean: .tox/ does not exist.")
        return

    size = _dir_size(tox_dir)
    shutil.rmtree(tox_dir)
    print(f"  Purged .tox/ entirely ({_sizeof_fmt(size)})")
    print("  Next 'tox' run will rebuild virtualenvs from scratch.")


def main() -> None:
    """Entry point for the tox cleanup script."""
    parser = argparse.ArgumentParser(description="Clean stale tox build artefacts.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Wipe entire .tox/ directory (rebuilds venvs on next run).",
    )
    args = parser.parse_args()

    # Find project root (parent of scripts/)
    project_root = Path(__file__).resolve().parent.parent
    tox_dir = project_root / ".tox"

    if not tox_dir.exists():
        print("No .tox/ directory found. Nothing to do.")
        sys.exit(0)

    print(f"Project root: {project_root}")
    print(f"Current .tox/ size: {_sizeof_fmt(_dir_size(tox_dir))}")
    print()

    if args.full:
        purge_full(tox_dir)
    else:
        purge_tmp_packages(tox_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
