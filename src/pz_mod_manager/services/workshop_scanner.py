from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PZ_APP_ID = "108600"


@dataclass
class WorkshopModInfo:
    """A single mod found inside a workshop item's directory."""

    mod_id: str
    name: str
    workshop_id: str


def scan_workshop_content(workshop_path: Path) -> list[WorkshopModInfo]:
    """Scan a Steam workshop content directory for PZ mod.info files.

    Args:
        workshop_path: Path to the workshop content root, e.g.
            /path/to/workshop-mods/content/108600/
            or /path/to/workshop-mods/ (will look for content/108600/ inside)

    Returns:
        List of WorkshopModInfo with the mod_id, name, and workshop_id for
        every mod found across all workshop items.
    """
    content_dir = _resolve_content_dir(workshop_path)
    if content_dir is None or not content_dir.is_dir():
        return []

    results: list[WorkshopModInfo] = []

    for item_dir in content_dir.iterdir():
        if not item_dir.is_dir() or not item_dir.name.isdigit():
            continue
        workshop_id = item_dir.name
        mods_dir = item_dir / "mods"
        if not mods_dir.is_dir():
            continue

        for mod_dir in mods_dir.iterdir():
            if not mod_dir.is_dir():
                continue
            info = _find_best_mod_info(mod_dir)
            if info:
                mod_id, name = info
                results.append(
                    WorkshopModInfo(
                        mod_id=mod_id,
                        name=name,
                        workshop_id=workshop_id,
                    )
                )

    return results


def build_mod_id_to_workshop_map(
    mods: list[WorkshopModInfo],
) -> dict[str, str]:
    """Build a mapping of mod_id -> workshop_id from scan results."""
    return {m.mod_id: m.workshop_id for m in mods}


def build_workshop_to_mod_ids_map(
    mods: list[WorkshopModInfo],
) -> dict[str, list[str]]:
    """Build a mapping of workshop_id -> [mod_id, ...] from scan results."""
    result: dict[str, list[str]] = {}
    for m in mods:
        result.setdefault(m.workshop_id, []).append(m.mod_id)
    return result


def _resolve_content_dir(path: Path) -> Path | None:
    """Try to find the content/108600/ directory from various starting points."""
    # Direct path to content/108600/
    if path.name == PZ_APP_ID and path.is_dir():
        return path
    # Path to content/ (look for 108600 inside)
    candidate = path / PZ_APP_ID
    if candidate.is_dir():
        return candidate
    # Path to workshop root (look for content/108600/)
    candidate = path / "content" / PZ_APP_ID
    if candidate.is_dir():
        return candidate
    return None


def _find_best_mod_info(mod_dir: Path) -> tuple[str, str] | None:
    """Find and parse the best mod.info file in a mod directory.

    Workshop items can have version-specific subdirectories (42/, 42.13/, etc.)
    with their own mod.info. We prefer the highest version, falling back to a
    root-level mod.info.

    Returns (mod_id, name) or None if no valid mod.info found.
    """
    # Collect all mod.info files
    info_files: list[tuple[str, Path]] = []
    root_info = mod_dir / "mod.info"
    if root_info.is_file():
        info_files.append(("", root_info))

    for subdir in mod_dir.iterdir():
        if subdir.is_dir():
            sub_info = subdir / "mod.info"
            if sub_info.is_file():
                info_files.append((subdir.name, sub_info))

    if not info_files:
        return None

    # Prefer versioned dirs (sorted descending) over root
    info_files.sort(key=lambda x: x[0], reverse=True)
    # Pick the first versioned one, or root if no versioned dirs
    _, best_file = info_files[0] if info_files[0][0] else info_files[-1]
    # Actually prefer highest version
    for version_name, path in info_files:
        if version_name:  # has a version dir
            best_file = path
            break

    return _parse_mod_info(best_file)


def _parse_mod_info(info_path: Path) -> tuple[str, str] | None:
    """Parse a mod.info file and extract id= and name= values."""
    try:
        text = info_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    mod_id = ""
    name = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("id="):
            mod_id = line.partition("=")[2].strip()
        elif line.startswith("name="):
            name = line.partition("=")[2].strip()

    if mod_id:
        return mod_id, name
    return None
