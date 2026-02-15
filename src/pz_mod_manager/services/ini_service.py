from __future__ import annotations

import os
import tempfile
from pathlib import Path


class IniService:
    """Reads and writes Project Zomboid server INI files.

    The PZ servertest.ini is a flat key=value file with no section headers.
    We preserve all lines exactly as-is except for the Mods= and WorkshopItems= lines.

    In B42+, mod IDs in the Mods= line are prefixed with a backslash:
        Mods=\\ModA;\\ModB;\\ModC
    We strip the prefix on load and add it back on save.
    """

    def load(self, file_path: str | Path) -> tuple[list[str], list[str]]:
        """Parse Mods= and WorkshopItems= from the INI file.

        Returns:
            (mod_ids, workshop_ids) - two lists of strings.
            Mod IDs have the B42+ backslash prefix stripped.
        """
        lines = self._read_lines(file_path)
        mod_ids: list[str] = []
        workshop_ids: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Mods="):
                raw = self._parse_semicolon_list(stripped)
                # Strip B42+ backslash prefix from each mod ID
                mod_ids = [mid.lstrip("\\") for mid in raw]
            elif stripped.startswith("WorkshopItems="):
                workshop_ids = self._parse_semicolon_list(stripped)

        return mod_ids, workshop_ids

    def save(
        self,
        file_path: str | Path,
        mod_ids: list[str],
        workshop_ids: list[str],
    ) -> None:
        """Write updated Mods= and WorkshopItems= lines, preserving all other content.

        Mod IDs are written with the B42+ backslash prefix.
        """
        file_path = Path(file_path)
        lines = self._read_lines(file_path)

        # B42+ format: each mod ID gets a backslash prefix
        formatted_mods = [f"\\{mid}" for mid in mod_ids if mid]
        mods_line = "Mods=" + ";".join(formatted_mods) + "\n"
        workshop_line = "WorkshopItems=" + ";".join(workshop_ids) + "\n"

        found_mods = False
        found_workshop = False
        new_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Mods="):
                new_lines.append(mods_line)
                found_mods = True
            elif stripped.startswith("WorkshopItems="):
                new_lines.append(workshop_line)
                found_workshop = True
            else:
                new_lines.append(line)

        if not found_mods:
            new_lines.append(mods_line)
        if not found_workshop:
            new_lines.append(workshop_line)

        # Atomic write: write to temp file then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=file_path.parent, suffix=".tmp", prefix=".pz_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            os.replace(tmp_path, file_path)
        except BaseException:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def read_bool(self, file_path: str | Path, key: str, default: bool = False) -> bool:
        """Read a boolean key=value from the INI file."""
        for line in self._read_lines(file_path):
            stripped = line.strip()
            if stripped.startswith(f"{key}="):
                _, _, value = stripped.partition("=")
                return value.strip().lower() == "true"
        return default

    def write_bool(self, file_path: str | Path, key: str, value: bool) -> None:
        """Write a boolean key=value in the INI file, preserving all other content."""
        file_path = Path(file_path)
        lines = self._read_lines(file_path)
        new_value = "true" if value else "false"
        found = False
        new_lines: list[str] = []

        for line in lines:
            if line.strip().startswith(f"{key}="):
                new_lines.append(f"{key}={new_value}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f"{key}={new_value}\n")

        fd, tmp_path = tempfile.mkstemp(
            dir=file_path.parent, suffix=".tmp", prefix=".pz_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            os.replace(tmp_path, file_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _read_lines(self, file_path: str | Path) -> list[str]:
        with open(file_path, encoding="utf-8") as f:
            return f.readlines()

    def _parse_semicolon_list(self, line: str) -> list[str]:
        """Split 'Key=val1;val2;val3' into ['val1', 'val2', 'val3'].

        Preserves empty entries in the middle to maintain positional
        correspondence between Mods= and WorkshopItems= lists.
        Only strips trailing empty entries (caused by trailing semicolons).
        """
        _, _, value = line.partition("=")
        if not value or not value.strip(";\\ "):
            return []
        items = value.split(";")
        # Strip trailing empties (from trailing semicolons) but keep internal ones
        while items and not items[-1]:
            items.pop()
        return items
