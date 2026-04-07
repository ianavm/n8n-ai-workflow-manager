"""Initialize the AWE memory directory structure.

Creates directories and empty index files as defined in MEMORY_MODEL.md.
Idempotent — safe to run multiple times.

Usage:
    python -m autonomous.scripts.init_memory
"""

from __future__ import annotations

import json
from pathlib import Path

MEMORY_ROOT = Path(__file__).parent.parent / "memory"

SUBDIRS = [
    "workflows",
    "incidents",
    "patterns",
    "decisions",
    "test_history",
    "specs",
    "recommendations",
    "deployments",
]


def init_memory_dirs(root: Path = MEMORY_ROOT) -> list[str]:
    """Create memory directory structure with empty index files.

    Returns list of directories created or verified.
    """
    created: list[str] = []
    root.mkdir(parents=True, exist_ok=True)

    for subdir in SUBDIRS:
        dir_path = root / subdir
        dir_path.mkdir(parents=True, exist_ok=True)

        index_path = dir_path / f"{subdir}_index.json"
        if not index_path.exists():
            index_path.write_text(
                json.dumps({}, indent=2), encoding="utf-8"
            )

        created.append(str(dir_path))

    return created


def main() -> None:
    dirs = init_memory_dirs()
    print(f"AWE memory initialized: {len(dirs)} directories ready")
    for d in dirs:
        print(f"  {d}")


if __name__ == "__main__":
    main()
