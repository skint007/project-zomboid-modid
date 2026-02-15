from pz_mod_manager.models.mod import Mod


class TestMod:
    def test_creation(self):
        mod = Mod(mod_id="Hydrocraft", workshop_id="2875848298")
        assert mod.mod_id == "Hydrocraft"
        assert mod.workshop_id == "2875848298"
        assert mod.name == ""
        assert mod.enabled is True

    def test_with_all_fields(self):
        mod = Mod(
            mod_id="TestMod",
            workshop_id="123",
            name="Test Mod Name",
            description="A test mod",
            enabled=False,
        )
        assert mod.name == "Test Mod Name"
        assert mod.enabled is False
