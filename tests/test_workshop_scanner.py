from pathlib import Path

import pytest

from pz_mod_manager.services.workshop_scanner import (
    WorkshopModInfo,
    build_mod_id_to_workshop_map,
    build_workshop_to_mod_ids_map,
    scan_workshop_content,
)


@pytest.fixture
def workshop_tree(tmp_path):
    """Create a minimal workshop content tree for testing."""
    content = tmp_path / "content" / "108600"

    # Workshop item 111 with one mod
    mod_a = content / "111" / "mods" / "ModA" / "42"
    mod_a.mkdir(parents=True)
    (mod_a / "mod.info").write_text("name=Mod A\nid=ModA\n")

    # Workshop item 222 with two mods
    mod_b = content / "222" / "mods" / "ModB" / "42.13"
    mod_b.mkdir(parents=True)
    (mod_b / "mod.info").write_text("name=Mod B\nid=ModB\n")

    mod_c = content / "222" / "mods" / "ModC"
    mod_c.mkdir(parents=True)
    (mod_c / "mod.info").write_text("name=Mod C\nid=ModC\n")

    # Workshop item 333 with versioned and root mod.info
    mod_d = content / "333" / "mods" / "ModD"
    mod_d.mkdir(parents=True)
    (mod_d / "mod.info").write_text("name=Mod D Old\nid=ModD\n")
    ver = mod_d / "42.13"
    ver.mkdir()
    (ver / "mod.info").write_text("name=Mod D New\nid=ModD\n")

    return tmp_path


class TestScanWorkshopContent:
    def test_finds_all_mods(self, workshop_tree):
        results = scan_workshop_content(workshop_tree)
        mod_ids = sorted(r.mod_id for r in results)
        assert mod_ids == ["ModA", "ModB", "ModC", "ModD"]

    def test_correct_workshop_ids(self, workshop_tree):
        results = scan_workshop_content(workshop_tree)
        by_mod = {r.mod_id: r.workshop_id for r in results}
        assert by_mod["ModA"] == "111"
        assert by_mod["ModB"] == "222"
        assert by_mod["ModC"] == "222"  # same workshop item as ModB
        assert by_mod["ModD"] == "333"

    def test_prefers_versioned_mod_info(self, workshop_tree):
        results = scan_workshop_content(workshop_tree)
        mod_d = next(r for r in results if r.mod_id == "ModD")
        assert mod_d.name == "Mod D New"

    def test_empty_dir(self, tmp_path):
        assert scan_workshop_content(tmp_path) == []

    def test_resolves_content_subdir(self, workshop_tree):
        # Pass the parent dir - scanner should find content/108600/ inside
        results = scan_workshop_content(workshop_tree)
        assert len(results) == 4


class TestBuildMaps:
    def test_mod_id_to_workshop(self):
        mods = [
            WorkshopModInfo(mod_id="A", name="", workshop_id="111"),
            WorkshopModInfo(mod_id="B", name="", workshop_id="222"),
        ]
        assert build_mod_id_to_workshop_map(mods) == {"A": "111", "B": "222"}

    def test_workshop_to_mod_ids(self):
        mods = [
            WorkshopModInfo(mod_id="A", name="", workshop_id="111"),
            WorkshopModInfo(mod_id="B", name="", workshop_id="222"),
            WorkshopModInfo(mod_id="C", name="", workshop_id="222"),
        ]
        result = build_workshop_to_mod_ids_map(mods)
        assert result["111"] == ["A"]
        assert sorted(result["222"]) == ["B", "C"]
