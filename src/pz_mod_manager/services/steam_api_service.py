from __future__ import annotations

import requests


class SteamApiError(Exception):
    pass


class SteamApiService:
    API_URL = "https://api.steampowered.com/IPublishedFileService/GetDetails/v1/"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def fetch_mod_details(self, workshop_ids: list[str]) -> list[dict]:
        """Batch fetch details for multiple workshop IDs.

        Returns a list of dicts with keys:
            publishedfileid, title, file_description, preview_url
        Only includes items that were found (result == 1).
        """
        if not workshop_ids:
            return []

        params: dict[str, str] = {"key": self._api_key}
        for i, wid in enumerate(workshop_ids):
            params[f"publishedfileids[{i}]"] = wid

        try:
            resp = requests.get(self.API_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise SteamApiError(f"Steam API request failed: {e}") from e

        data = resp.json()
        details = data.get("response", {}).get("publishedfiledetails", [])

        results = []
        for item in details:
            if item.get("result") == 1:
                results.append(
                    {
                        "publishedfileid": item.get("publishedfileid", ""),
                        "title": item.get("title", ""),
                        "file_description": item.get("file_description", ""),
                        "preview_url": item.get("preview_url", ""),
                    }
                )
        return results

    def fetch_single_mod(self, workshop_id: str) -> dict | None:
        """Fetch details for a single workshop ID. Returns None if not found."""
        results = self.fetch_mod_details([workshop_id])
        return results[0] if results else None
