"""
Apple App Store data fetcher using iTunes Search & Lookup APIs.
Free, public, no API key required.
API docs: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/
"""

import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

_ITUNES_BASE = "https://itunes.apple.com"


# ─────────────────────────────────────────────
# CACHE HELPERS
# ─────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)
    return CACHE_DIR / f"ios_{safe}.json"


def _load_cache(key: str, max_age_minutes: int = 60):
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        try:
            p.unlink()
        except Exception:
            pass
        return None
    age = (datetime.now().timestamp() - data.get("_cached_at", 0)) / 60
    if age > max_age_minutes:
        return None
    return data


def _save_cache(key: str, data: dict):
    data["_cached_at"] = datetime.now().timestamp()
    _cache_path(key).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _request(url: str) -> dict:
    """HTTP GET → parsed JSON. Raises on error."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ASO-Pro/1.0 (App Store Optimization Tool)"},
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─────────────────────────────────────────────
# NORMALIZATION
# ─────────────────────────────────────────────

def _normalize(raw: dict) -> dict:
    """Map iTunes API fields → consistent internal dict."""
    price = float(raw.get("price") or 0)
    size_bytes = int(raw.get("fileSizeBytes") or 0)
    size_mb = round(size_bytes / 1_048_576, 1) if size_bytes else 0

    description = raw.get("description", "") or ""
    # Short summary = first 80 chars of description (no dedicated field in iTunes API)
    summary = description[:80].strip()
    if len(description) > 80:
        summary = summary.rsplit(" ", 1)[0] + "…"

    score = round(float(raw.get("averageUserRating") or 0), 2)
    cv_score = round(float(raw.get("averageUserRatingForCurrentVersion") or 0), 2)

    return {
        "bundle_id": raw.get("bundleId", ""),
        "package_id": raw.get("bundleId", ""),   # alias so generic code works
        "apple_id": raw.get("trackId", 0),
        "title": raw.get("trackName", "") or "",
        "developer": raw.get("sellerName", "") or raw.get("artistName", ""),
        "developer_id": raw.get("artistId", 0),
        "description": description,
        "summary": summary,
        "score": score,
        "ratings": int(raw.get("userRatingCount") or 0),
        "current_version_score": cv_score,
        "current_version_ratings": int(raw.get("userRatingCountForCurrentVersion") or 0),
        "category": raw.get("primaryGenreName", "") or "",
        "genres": raw.get("genres", []),
        "price": price,
        "free": price == 0,
        "formatted_price": raw.get("formattedPrice", "Free") or "Free",
        "content_rating": raw.get("contentAdvisoryRating", "") or "",
        "version": raw.get("version", "") or "",
        "min_os": raw.get("minimumOsVersion", "") or "",
        "size_bytes": size_bytes,
        "size_mb": size_mb,
        "released": raw.get("releaseDate", "") or "",
        "updated": raw.get("currentVersionReleaseDate", "") or "",
        "icon": (
            raw.get("artworkUrl100", "")
            or raw.get("artworkUrl60", "")
            or ""
        ),
        "screenshots": raw.get("screenshotUrls", []),
        "ipad_screenshots": raw.get("ipadScreenshotUrls", []),
        "store_url": raw.get("trackViewUrl", "") or "",
        "languages": raw.get("languageCodesISO2A", []),
        "features": raw.get("features", []),
        "supported_devices": raw.get("supportedDevices", [])[:5],  # trim long list
        "installs": "",   # not available on iOS App Store
        "histogram": {},  # not available via iTunes API
        "_platform": "ios",
        "_fetched_at": datetime.now().isoformat(),
        "_from_cache": False,
    }


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def validate_bundle_id(bundle_id: str) -> tuple[bool, str]:
    """Validate iOS bundle ID format (e.g. com.example.app)."""
    if not bundle_id or not bundle_id.strip():
        return False, "Bundle ID cannot be empty."
    clean = bundle_id.strip()
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$', clean):
        return (
            False,
            f"'{clean}' is not a valid iOS bundle ID. Expected: com.example.app",
        )
    return True, ""


def search_ios_apps(query: str, country: str = "us", limit: int = 10) -> list:
    """
    Search iOS apps via iTunes Search API.
    Returns list of normalized app dicts.
    """
    cache_key = f"search_{query}_{country}_{limit}"
    cached = _load_cache(cache_key, max_age_minutes=30)
    if cached:
        return cached.get("results", [])

    params = urllib.parse.urlencode({
        "term": query,
        "entity": "software",
        "country": country,
        "limit": min(limit, 200),
    })
    data = _request(f"{_ITUNES_BASE}/search?{params}")
    results = [_normalize(r) for r in data.get("results", []) if r.get("bundleId")]
    _save_cache(cache_key, {"results": results})
    return results


def fetch_ios_app(identifier: str, country: str = "us") -> dict:
    """
    Fetch a single iOS app by bundle ID, numeric Apple ID, or search term.
    Tries bundle ID lookup → numeric ID lookup → search fallback.
    """
    cache_key = f"app_{identifier}_{country}"
    cached = _load_cache(cache_key)
    if cached:
        cached["_from_cache"] = True
        return cached

    raw = None

    # 1. Bundle ID lookup (com.example.app)
    looks_like_bundle = "." in identifier and " " not in identifier and not identifier.isdigit()
    if looks_like_bundle:
        try:
            params = urllib.parse.urlencode({"bundleId": identifier, "country": country})
            resp = _request(f"{_ITUNES_BASE}/lookup?{params}")
            if resp.get("resultCount", 0) > 0:
                raw = resp["results"][0]
        except Exception:
            pass

    # 2. Numeric Apple App ID
    if raw is None and identifier.isdigit():
        try:
            params = urllib.parse.urlencode({"id": identifier, "country": country})
            resp = _request(f"{_ITUNES_BASE}/lookup?{params}")
            if resp.get("resultCount", 0) > 0:
                raw = resp["results"][0]
        except Exception:
            pass

    # 3. Search fallback — return first result
    if raw is None:
        results = search_ios_apps(identifier, country=country, limit=1)
        if not results:
            raise RuntimeError(f"App '{identifier}' not found on App Store.")
        return results[0]

    result = _normalize(raw)
    _save_cache(cache_key, result)
    return result


def extract_bundle_from_url(text: str) -> str:
    """
    Extract iOS bundle ID or Apple ID from App Store URL.
    e.g. https://apps.apple.com/us/app/instagram/id389801252 → "389801252"
    Returns input unchanged if no match found.
    """
    # /id{numeric}
    m = re.search(r'/id(\d+)', text)
    if m:
        return m.group(1)
    return text.strip()
