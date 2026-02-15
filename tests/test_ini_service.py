import os
from pathlib import Path

import pytest

from pz_mod_manager.services.ini_service import IniService

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def service():
    return IniService()


@pytest.fixture
def sample_ini(tmp_path):
    """Copy sample INI to a temp dir so tests can modify it."""
    src = FIXTURES / "sample_servertest.ini"
    dst = tmp_path / "servertest.ini"
    dst.write_text(src.read_text())
    return dst


class TestLoad:
    def test_loads_mod_ids(self, service, sample_ini):
        mod_ids, _ = service.load(sample_ini)
        assert mod_ids == ["Hydrocraft", "BB_CommonSense", "SuperSurvivalMod"]

    def test_loads_workshop_ids(self, service, sample_ini):
        _, workshop_ids = service.load(sample_ini)
        assert workshop_ids == ["2875848298", "3475754603", "1234567890"]

    def test_empty_mods(self, service, tmp_path):
        ini = tmp_path / "empty.ini"
        ini.write_text("Mods=\nWorkshopItems=\n")
        mod_ids, workshop_ids = service.load(ini)
        assert mod_ids == []
        assert workshop_ids == []

    def test_trailing_semicolons(self, service, tmp_path):
        ini = tmp_path / "trailing.ini"
        ini.write_text("Mods=modA;modB;\nWorkshopItems=111;222;\n")
        mod_ids, workshop_ids = service.load(ini)
        assert mod_ids == ["modA", "modB"]
        assert workshop_ids == ["111", "222"]

    def test_missing_keys(self, service, tmp_path):
        ini = tmp_path / "nokeys.ini"
        ini.write_text("SomeOtherSetting=value\n")
        mod_ids, workshop_ids = service.load(ini)
        assert mod_ids == []
        assert workshop_ids == []

    def test_mismatched_lengths(self, service, tmp_path):
        """PZ allows different-length Mods= and WorkshopItems= lists."""
        ini = tmp_path / "mismatch.ini"
        ini.write_text("Mods=modA;modB;modC\nWorkshopItems=111;222\n")
        mod_ids, workshop_ids = service.load(ini)
        assert mod_ids == ["modA", "modB", "modC"]
        assert workshop_ids == ["111", "222"]

    def test_only_semicolons(self, service, tmp_path):
        """A line with only semicolons should parse as empty."""
        ini = tmp_path / "semis.ini"
        ini.write_text("Mods=;;;\nWorkshopItems=\n")
        mod_ids, workshop_ids = service.load(ini)
        assert mod_ids == []
        assert workshop_ids == []

    def test_b42_backslash_prefix(self, service, tmp_path):
        """B42+ format prefixes each mod ID with a backslash."""
        ini = tmp_path / "b42.ini"
        ini.write_text("Mods=\\ModA;\\ModB;\\ModC\nWorkshopItems=111;222;333\n")
        mod_ids, workshop_ids = service.load(ini)
        assert mod_ids == ["ModA", "ModB", "ModC"]
        assert workshop_ids == ["111", "222", "333"]

    def test_mixed_old_and_new_format(self, service, tmp_path):
        """Handle mix of prefixed and non-prefixed mod IDs."""
        ini = tmp_path / "mixed.ini"
        ini.write_text("Mods=\\ModA;ModB;\\ModC\nWorkshopItems=111;222;333\n")
        mod_ids, _ = service.load(ini)
        assert mod_ids == ["ModA", "ModB", "ModC"]


class TestSave:
    def test_preserves_other_lines(self, service, sample_ini):
        service.save(sample_ini, ["NewMod"], ["999"])
        content = sample_ini.read_text()
        assert "PVPMelee=true" in content
        assert "MaxPlayers=32" in content
        assert "SteamScoreboard=true" in content

    def test_writes_b42_format(self, service, sample_ini):
        """Save writes mod IDs with B42+ backslash prefix."""
        service.save(sample_ini, ["ModA", "ModB"], ["111", "222"])
        content = sample_ini.read_text()
        assert "Mods=\\ModA;\\ModB" in content

    def test_roundtrip(self, service, sample_ini):
        """Save then load returns the same mod IDs (without backslash prefix)."""
        service.save(sample_ini, ["ModA", "ModB"], ["111", "222"])
        mod_ids, workshop_ids = service.load(sample_ini)
        assert mod_ids == ["ModA", "ModB"]
        assert workshop_ids == ["111", "222"]

    def test_writes_empty_lists(self, service, sample_ini):
        service.save(sample_ini, [], [])
        mod_ids, workshop_ids = service.load(sample_ini)
        assert mod_ids == []
        assert workshop_ids == []

    def test_adds_missing_keys(self, service, tmp_path):
        ini = tmp_path / "nokeys.ini"
        ini.write_text("SomeOtherSetting=value\n")
        service.save(ini, ["TestMod"], ["123"])
        content = ini.read_text()
        assert "Mods=\\TestMod" in content
        assert "WorkshopItems=123" in content
        assert "SomeOtherSetting=value" in content

    def test_atomic_write(self, service, sample_ini):
        """Verify no temp files are left behind after a successful save."""
        parent = sample_ini.parent
        service.save(sample_ini, ["X"], ["1"])
        tmp_files = [f for f in parent.iterdir() if f.suffix == ".tmp"]
        assert tmp_files == []
