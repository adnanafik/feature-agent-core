"""Shared helper for applying code/test file changes from LLM output."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ApplyChangesError(Exception):
    """Raised when a change cannot be applied (missing required fields, etc.)."""


def apply_changes(
    repo_path: Path, changes: list[dict[str, Any]]
) -> tuple[int, list[str]]:
    """Apply a list of full-file writes.

    Each change must provide `path` and `new_content`. The target file is
    overwritten (or created) with `new_content`. Returns
    (files_written, files_skipped_as_noop).
    """
    written = 0
    skipped: list[str] = []
    for change in changes:
        path_str = change.get("path", "")
        if not path_str:
            continue
        if "new_content" not in change:
            raise ApplyChangesError(
                f"Change for {path_str} is missing required field `new_content`"
            )
        new_content = change.get("new_content", "")
        file_path = repo_path / path_str
        if file_path.exists() and file_path.read_text(errors="replace") == new_content:
            skipped.append(path_str)
            continue
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(new_content)
        written += 1
    return written, skipped
