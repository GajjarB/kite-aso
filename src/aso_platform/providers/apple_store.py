"""Public Apple iTunes Lookup/Search provider."""

from __future__ import annotations

import requests


class AppleLookupProvider:
    """Adapter over Apple's public iTunes Search/Lookup API."""

    source_id = "apple_itunes_lookup_api"

    def lookup(self, identifier: str, country: str = "us", entity: str = "software") -> dict:
        params = {"country": country, "entity": entity}
        if identifier.isdigit():
            params["id"] = identifier
        else:
            params["bundleId"] = identifier
        response = requests.get("https://itunes.apple.com/lookup", params=params, timeout=12)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        return results[0] if results else {}

    def search(self, term: str, country: str = "us", limit: int = 10, entity: str = "software") -> list[dict]:
        response = requests.get(
            "https://itunes.apple.com/search",
            params={"term": term, "country": country, "entity": entity, "limit": limit},
            timeout=12,
        )
        response.raise_for_status()
        return response.json().get("results", [])

