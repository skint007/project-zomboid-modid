from pz_mod_manager.utils.url_parser import extract_workshop_id


class TestExtractWorkshopId:
    def test_plain_numeric_id(self):
        assert extract_workshop_id("2875848298") == "2875848298"

    def test_full_url(self):
        url = "https://steamcommunity.com/sharedfiles/filedetails/?id=2875848298"
        assert extract_workshop_id(url) == "2875848298"

    def test_url_with_extra_params(self):
        url = "https://steamcommunity.com/sharedfiles/filedetails/?id=2875848298&searchtext=zomboid"
        assert extract_workshop_id(url) == "2875848298"

    def test_url_with_id_not_first(self):
        url = "https://steamcommunity.com/sharedfiles/filedetails/?searchtext=zomboid&id=2875848298"
        assert extract_workshop_id(url) == "2875848298"

    def test_empty_string(self):
        assert extract_workshop_id("") is None

    def test_whitespace(self):
        assert extract_workshop_id("  2875848298  ") == "2875848298"

    def test_invalid_text(self):
        assert extract_workshop_id("not a url or id") is None

    def test_http_url(self):
        url = "http://steamcommunity.com/sharedfiles/filedetails/?id=123456"
        assert extract_workshop_id(url) == "123456"
