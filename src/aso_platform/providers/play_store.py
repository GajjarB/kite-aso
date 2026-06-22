"""Public Play Store provider adapter."""

from __future__ import annotations

from core.fetcher import fetch_app_details, search_apps

from ..models import AppDetails


class PlayStorePublicProvider:
    """Adapter over the existing fetcher for public app metadata."""

    source_id = "google_play_public_store"

    def fetch_app(self, package_id: str, lang: str = "en", country: str = "us") -> AppDetails:
        raw = fetch_app_details(package_id, lang=lang, country=country)
        return AppDetails.from_mapping(raw)


class PlayStoreSearchProvider:
    """Adapter over public Play Store search results."""

    source_id = "google_play_public_search"

    def search(self, query: str, n_hits: int = 20, lang: str = "en", country: str = "us") -> list[dict]:
        return search_apps(query, n_hits=n_hits, lang=lang, country=country)
