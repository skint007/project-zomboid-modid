from __future__ import annotations

import os
import tempfile
from pathlib import Path


class IniService:
    """Reads and writes Project Zomboid server INI files.

    The PZ servertest.ini is a flat key=value file with no section headers.
    We preserve all lines exactly as-is except for the Mods= and WorkshopItems= lines.
    """

    def load(self, file_path: str | Path) -> tuple[list[str], list[str]]:
        """Parse Mods= and WorkshopItems= from the INI file.

        Returns:
            (mod_ids, workshop_ids) - two lists of strings.
        """
        lines = self._read_lines(file_path)
        mod_ids: list[str] = []
        workshop_ids: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Mods="):
                mod_ids = self._parse_semicolon_list(stripped)
            elif stripped.startswith("WorkshopItems="):
                workshop_ids = self._parse_semicolon_list(stripped)

        return mod_ids, workshop_ids

    def save(
        self,
        file_path: str | Path,
        mod_ids: list[str],
        workshop_ids: list[str],
    ) -> None:
        """Write updated Mods= and WorkshopItems= lines, preserving all other content."""
        file_path = Path(file_path)
        lines = self._read_lines(file_path)

        mods_line = "Mods=" + ";".join(mod_ids) + "\n"
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

    def _read_lines(self, file_path: str | Path) -> list[str]:
        with open(file_path, encoding="utf-8") as f:
            return f.readlines()

    def _parse_semicolon_list(self, line: str) -> list[str]:
        """Split 'Key=val1;val2;val3' into ['val1', 'val2', 'val3'], filtering empties."""
        _, _, value = line.partition("=")
        return [item for item in value.split(";") if item]
