from unittest.mock import MagicMock, patch

import pytest

from pz_mod_manager.services.steam_api_service import SteamApiError, SteamApiService


@pytest.fixture
def service():
    return SteamApiService(api_key="test_key")


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status.return_value = None
    return mock


class TestFetchModDetails:
    @patch("pz_mod_manager.services.steam_api_service.requests.get")
    def test_returns_details(self, mock_get, service):
        mock_get.return_value = _mock_response(
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": 1,
                            "publishedfileid": "123",
                            "title": "Test Mod",
                            "file_description": "A mod",
                            "preview_url": "https://example.com/img.jpg",
                        }
                    ]
                }
            }
        )
        results = service.fetch_mod_details(["123"])
        assert len(results) == 1
        assert results[0]["title"] == "Test Mod"
        assert results[0]["publishedfileid"] == "123"

    @patch("pz_mod_manager.services.steam_api_service.requests.get")
    def test_skips_not_found(self, mock_get, service):
        mock_get.return_value = _mock_response(
            {
                "response": {
                    "publishedfiledetails": [
                        {"result": 9, "publishedfileid": "999"}
                    ]
                }
            }
        )
        results = service.fetch_mod_details(["999"])
        assert results == []

    def test_empty_list(self, service):
        assert service.fetch_mod_details([]) == []

    @patch("pz_mod_manager.services.steam_api_service.requests.get")
    def test_network_error(self, mock_get, service):
        import requests

        mock_get.side_effect = requests.ConnectionError("fail")
        with pytest.raises(SteamApiError, match="Steam API request failed"):
            service.fetch_mod_details(["123"])


class TestFetchSingleMod:
    @patch("pz_mod_manager.services.steam_api_service.requests.get")
    def test_returns_single(self, mock_get, service):
        mock_get.return_value = _mock_response(
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": 1,
                            "publishedfileid": "456",
                            "title": "Single Mod",
                            "file_description": "",
                            "preview_url": "",
                        }
                    ]
                }
            }
        )
        result = service.fetch_single_mod("456")
        assert result is not None
        assert result["title"] == "Single Mod"

    @patch("pz_mod_manager.services.steam_api_service.requests.get")
    def test_returns_none_when_not_found(self, mock_get, service):
        mock_get.return_value = _mock_response(
            {"response": {"publishedfiledetails": [{"result": 9}]}}
        )
        assert service.fetch_single_mod("999") is None
