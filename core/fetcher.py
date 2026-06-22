"""
Real Play Store data fetcher using google-play-scraper.
No fake data. All results come from live Play Store.
"""

import json
import time
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

try:
    from google_play_scraper import app as gps_app, search as gps_search, reviews as gps_reviews
    try:
        from google_play_scraper import Sort as GPSSort
    except ImportError:
        GPSSort = None
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    GPSSort = None

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def validate_package_id(package_id: str) -> tuple[bool, str]:
    """Validate Android package ID format (e.g. com.example.app)."""
    if not package_id or not package_id.strip():
        return False, "Package ID cannot be empty."
    clean = package_id.strip()
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$', clean):
        return False, f"'{clean}' is not a valid Android package ID. Expected format: com.example.app"
    return True, ""


def _cache_path(key: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)
    return CACHE_DIR / f"{safe}.json"


def _load_cache(key: str, max_age_minutes: int = 60):
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except Exception:
        # Corrupted cache file — remove and treat as cache miss
        try:
            p.unlink()
        except Exception:
            pass
        return None
    # Normalize histogram in cached data if needed (list -> dict)
    try:
        h = data.get("histogram")
        if isinstance(h, list):
            _hist = {}
            if len(h) >= 5:
                for i, val in enumerate(h[:5]):
                    _hist[str(i + 1)] = val or 0
            else:
                for i, val in enumerate(h):
                    _hist[str(i + 1)] = val or 0
            data["histogram"] = _hist
        elif isinstance(h, dict):
            data["histogram"] = {str(k): (v or 0) for k, v in h.items()}
    except Exception:
        pass

    # Coerce common fields to safe defaults to avoid NoneType formatting
    try:
        if data.get("score") is None:
            data["score"] = 0
        if data.get("ratings") is None:
            data["ratings"] = 0
        if data.get("reviews") is None:
            data["reviews"] = 0
        if data.get("free") is None:
            data["free"] = True
    except Exception:
        pass
    age = (datetime.now().timestamp() - data.get("_cached_at", 0)) / 60
    if age > max_age_minutes:
        return None
    return data


def _save_cache(key: str, data: dict):
    data["_cached_at"] = datetime.now().timestamp()
    _cache_path(key).write_text(json.dumps(data, indent=2))


def fetch_app_details(package_id: str, lang="en", country="us") -> dict:
    """Fetch full app details from Play Store. Returns real data."""
    cache_key = f"app_{package_id}_{lang}_{country}"
    cached = _load_cache(cache_key)
    if cached:
        cached["_from_cache"] = True
        return cached

    if not GPS_AVAILABLE:
        raise RuntimeError("google-play-scraper not installed. Run: pip install google-play-scraper")

    raw = gps_app(package_id, lang=lang, country=country)
    # Coerce values to safe defaults to avoid NoneType formatting errors
    # Normalize histogram separately to keep the dict literal clean
    _raw_hist = raw.get("histogram")
    if isinstance(_raw_hist, list):
        _hist = {}
        if len(_raw_hist) >= 5:
            for i, val in enumerate(_raw_hist[:5]):
                _hist[str(i + 1)] = val or 0
        else:
            for i, val in enumerate(_raw_hist):
                _hist[str(i + 1)] = val or 0
    elif isinstance(_raw_hist, dict):
        _hist = {str(k): (v or 0) for k, v in _raw_hist.items()}
    else:
        _hist = {}

    result = {
        "package_id": package_id,
        "title": raw.get("title") or "",
        "summary": raw.get("summary") or "",
        "description": raw.get("description") or "",
        "score": raw.get("score") or 0,
        "ratings": raw.get("ratings") or 0,
        "reviews": raw.get("reviews") or 0,
        "installs": raw.get("installs") or "",
        "min_installs": raw.get("minInstalls") or 0,
        "category": raw.get("genre") or "",
        "category_id": raw.get("genreId") or "",
        "developer": raw.get("developer") or "",
        "developer_email": raw.get("developerEmail") or "",
        "price": raw.get("price") or 0,
        "free": raw.get("free") if raw.get("free") is not None else True,
        "content_rating": raw.get("contentRating") or "",
        "updated": raw.get("updated") or "",
        "version": raw.get("version") or "",
        "android_version": raw.get("androidVersion") or "",
        "icon": raw.get("icon") or "",
        "screenshots": raw.get("screenshots") or [],
        "video": raw.get("video") or "",
        "contains_ads": raw.get("containsAds") or False,
        "released": raw.get("released") or "",
        "histogram": _hist,
        "has_rating": raw.get("score") is not None,
        "_fetched_at": datetime.now().isoformat(),
        "_from_cache": False,
    }
    _save_cache(cache_key, result)
    return result


def search_apps(query: str, n_hits: int = 10, lang="en", country="us") -> list:
    """Search Play Store and return ranked results."""
    cache_key = f"search_{query}_{n_hits}_{lang}_{country}"
    cached = _load_cache(cache_key, max_age_minutes=30)
    if cached:
        return cached.get("results", [])

    if not GPS_AVAILABLE:
        raise RuntimeError("google-play-scraper not installed.")

    raw = gps_search(query, lang=lang, country=country, n_hits=n_hits)
    results = []
    for r in raw:
        results.append({
            "package_id": r.get("appId", ""),
            "title": r.get("title", ""),
            "developer": r.get("developer", ""),
            "score": r.get("score", 0),
            "installs": r.get("installs", ""),
            "free": r.get("free", True),
            "summary": r.get("summary", ""),
            "category": r.get("genre", ""),
            "icon": r.get("icon", ""),
        })

    _save_cache(cache_key, {"results": results})
    return results


def fetch_reviews(package_id: str, count: int = 100, lang="en", country="us") -> list:
    """Fetch real user reviews for NLP keyword mining."""
    cache_key = f"reviews_{package_id}_{count}_{lang}"
    cached = _load_cache(cache_key, max_age_minutes=120)
    if cached:
        return cached.get("reviews", [])

    if not GPS_AVAILABLE:
        raise RuntimeError("google-play-scraper not installed.")

    sort_value = GPSSort.MOST_RELEVANT if GPSSort is not None else 1

    result, _ = gps_reviews(
        package_id,
        lang=lang,
        country=country,
        count=count,
        sort=sort_value,
    )
    clean = []
    for r in result:
        clean.append({
            "text": r.get("content", ""),
            "score": r.get("score", 0),
            "thumbs_up": r.get("thumbsUpCount", 0),
            "at": str(r.get("at", "")),
        })

    _save_cache(cache_key, {"reviews": clean})
    return clean


def fetch_similar_apps(package_id: str, lang: str = "en", country: str = "us") -> list:
    """
    Find apps similar to the given package by searching with its title + category.
    Uses the approved search_apps() source — no extra dependency needed.
    Returns list of app dicts (same shape as search_apps results), excluding the source app.
    """
    if not GPS_AVAILABLE:
        return []

    cache_key = f"similar_{package_id}_{lang}_{country}"
    cached = _load_cache(cache_key, max_age_minutes=120)
    if cached:
        return cached.get("results", [])

    # Fetch source app to get title + category for query building
    try:
        source = gps_app(package_id, lang=lang, country=country)
        title    = source.get("title", "") or ""
        genre    = source.get("genre", "") or ""
        category = source.get("genreId", "") or ""
    except Exception:
        return []

    # Build 2-3 search queries from title + genre
    seen: set = set()
    seen.add(package_id)
    results: list = []

    queries = []
    if genre:
        queries.append(genre)
    # First 2-3 meaningful words of the title
    title_words = [w for w in title.lower().split() if len(w) > 3 and w.isalpha()]
    if title_words:
        queries.append(" ".join(title_words[:2]))
    if category:
        queries.append(category.lower().replace("_", " "))

    for q in queries[:3]:
        try:
            batch = gps_search(q, lang=lang, country=country, n_hits=8)
            for r in batch:
                pkg = r.get("appId", "")
                if not pkg or pkg in seen:
                    continue
                seen.add(pkg)
                results.append({
                    "package_id": pkg,
                    "title":     r.get("title", "") or "",
                    "developer": r.get("developer", "") or "",
                    "score":     r.get("score", 0) or 0,
                    "installs":  r.get("installs", "") or "",
                    "free":      r.get("free", True),
                    "summary":   r.get("summary", "") or "",
                    "category":  r.get("genre", "") or "",
                    "icon":      r.get("icon", "") or "",
                })
        except Exception:
            pass
        time.sleep(0.3)

    _save_cache(cache_key, {"results": results})
    return results


def get_autocomplete_keywords(query: str, lang: str = "en", country: str = "us") -> list:
    """
    Extract keyword suggestions from Play Store search result titles/summaries.
    The old market.android.com suggest endpoint was decommissioned in 2012 — this
    uses approved search_apps() as the live signal source instead.
    """
    if not GPS_AVAILABLE:
        return []

    suggestions = []
    seen: set[str] = set()

    # Run search for the base query and a few suffix variants
    suffixes = ["", " app", " free", " pro", " offline"]
    for suffix in suffixes[:3]:
        term = f"{query}{suffix}".strip()
        try:
            results = search_apps(term, n_hits=8, lang=lang, country=country)
        except Exception:
            results = []
        time.sleep(0.25)
        for r in results:
            for field in ("title", "summary"):
                text = (r.get(field) or "").lower()
                words = re.findall(r'\b[a-z]{3,}\b', text)
                for w in words:
                    if w not in seen and w not in {query.lower()}:
                        seen.add(w)
                # Extract bigrams from title
                title_words = re.findall(r'\b[a-z]{3,}\b', (r.get("title") or "").lower())
                for i in range(len(title_words) - 1):
                    phrase = f"{title_words[i]} {title_words[i+1]}"
                    if phrase not in seen:
                        seen.add(phrase)
                        suggestions.append(phrase)

    return suggestions[:30]
