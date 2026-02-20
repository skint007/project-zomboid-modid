from __future__ import annotations

import requests

from pz_mod_manager.utils.constants import STEAM_WORKSHOP_PZ_APP_ID


class SteamApiError(Exception):
    pass


class SteamApiService:
    API_URL = "https://api.steampowered.com/IPublishedFileService/GetDetails/v1/"
    QUERY_URL = "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
    TAG_LIST_URL = "https://api.steampowered.com/IPublishedFileService/GetTagList/v1/"

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

    def search_mods(
        self,
        text: str,
        tags: list[str] | None = None,
        page: int = 1,
        num_per_page: int = 20,
    ) -> dict:
        """Search Steam Workshop for PZ mods by text and optional tags.

        Returns a dict with keys:
            total (int): total number of matching results
            results (list[dict]): each dict has keys:
                publishedfileid, title, short_description,
                file_description, preview_url, tags (list[str]),
                subscriptions (int)
        Raises SteamApiError on failure.
        """
        params: dict[str, str] = {
            "key": self._api_key,
            "query_type": "12",
            "search_text": text,
            "appid": STEAM_WORKSHOP_PZ_APP_ID,
            "return_details": "true",
            "return_tags": "true",
            "numperpage": str(num_per_page),
            "page": str(page),
        }
        if tags:
            for i, tag in enumerate(tags):
                params[f"requiredtags[{i}]"] = tag

        try:
            resp = requests.get(self.QUERY_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise SteamApiError(f"Steam API request failed: {e}") from e

        response = resp.json().get("response", {})
        total = int(response.get("total", 0))
        raw_items = response.get("publishedfiledetails", [])

        results = []
        for item in raw_items:
            tag_list = [t["tag"] for t in item.get("tags", []) if "tag" in t]
            results.append({
                "publishedfileid": item.get("publishedfileid", ""),
                "title": item.get("title", ""),
                "short_description": item.get("short_description", ""),
                "file_description": item.get("file_description", ""),
                "preview_url": item.get("preview_url", ""),
                "tags": tag_list,
                "subscriptions": int(item.get("subscriptions", 0)),
            })

        return {"total": total, "results": results}

    def fetch_tags(self) -> list[str]:
        """Fetch available Steam Workshop tags for PZ, sorted by popularity.

        Returns a list of tag name strings.
        Raises SteamApiError on failure.
        """
        params = {
            "key": self._api_key,
            "appid": STEAM_WORKSHOP_PZ_APP_ID,
            "language": "english",
        }
        try:
            resp = requests.get(self.TAG_LIST_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise SteamApiError(f"Steam API request failed: {e}") from e

        tags = resp.json().get("response", {}).get("tags", [])
        tags.sort(key=lambda t: int(t.get("count", 0)), reverse=True)
        return [t["tag"] for t in tags if "tag" in t]
