"""
Keyword Intelligence Engine
- Mines real user reviews for keyword extraction
- Uses Google Trends (pytrends) for trend data
- Analyzes competitor descriptions for keyword gaps
- Scores keywords by relevance + trend momentum
"""

import re
import json
import time
from difflib import get_close_matches
from collections import Counter
from pathlib import Path
from datetime import datetime


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "this", "that", "are",
    "was", "were", "be", "been", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "not", "no",
    "so", "if", "as", "up", "out", "my", "your", "our", "i", "we", "you",
    "he", "she", "they", "me", "us", "him", "her", "them", "just", "also",
    "very", "more", "most", "all", "any", "some", "than", "then", "about",
    "into", "over", "after", "before", "between", "through", "during", "app",
    "apps", "use", "used", "using", "get", "got", "good", "great", "really",
    "like", "love", "need", "want", "makes", "make", "made", "works", "work",
    "even", "still", "much", "many", "every", "other", "what", "when", "how",
    "where", "which", "who", "there", "here", "each", "only", "new", "well",
}


COMMON_KEYWORD_FIXES = {
    "calc": "calculator",
    "calci": "calculator",
    "calculater": "calculator",
    "claculator": "calculator",
    "paece": "percentage",
    "perc": "percentage",
    "percent": "percentage",
    "bmi": "bmi",
    "gpa": "gpa",
}

NOISE_TERMS = {"etc", "rtc"}

# Short terms worth keeping in keyword analysis (2-char abbreviations users search)
SHORT_KEEP = {"ai", "qr", "vpn", "pdf", "apk", "sdk", "ide", "api", "cms", "crm", "erp", "ocr"}

CALCULATOR_SEED_MAP = {
    "calculator app": "calculator",
    "calculator": "calculator",
    "scientific calculator": "scientific calculator",
    "unit converter": "unit converter",
    "converter": "unit converter",
    "bmi": "bmi calculator",
    "age": "age calculator",
    "gpa": "gpa calculator",
    "percentage": "percentage calculator",
    "loan": "loan calculator",
    "saving": "savings calculator",
    "savings": "savings calculator",
}

DOMAIN_TERMS = sorted(set(CALCULATOR_SEED_MAP) | set(COMMON_KEYWORD_FIXES.values()) | {
    "scientific", "converter", "finance", "emi", "mortgage", "discount", "tip",
    "currency", "math", "algebra", "geometry", "tax",
})

CATEGORY_ALIASES = {
    "tool": "tools",
    "tools": "tools",
    "utility": "tools",
    "utilities": "tools",
    "productivity": "productivity",
    "finance": "finance",
    "financial": "finance",
    "health": "health_fitness",
    "fitness": "health_fitness",
    "health fitness": "health_fitness",
    "education": "education",
    "learning": "education",
    "business": "business",
    "photo": "photo_video",
    "video": "photo_video",
    "photo video": "photo_video",
    "entertainment": "entertainment",
    "media": "entertainment",
    "streaming": "entertainment",
    "music": "music_audio",
    "audio": "music_audio",
    "music audio": "music_audio",
    "podcast": "music_audio",
    "game": "games",
    "games": "games",
    "gaming": "games",
    "puzzle": "games",
    "arcade": "games",
    "news": "news",
    "newspaper": "news",
    "rss": "news",
    "travel": "travel",
    "navigation": "travel",
    "maps": "travel",
    "shopping": "shopping",
    "ecommerce": "shopping",
    "store": "shopping",
    "social": "social",
    "social network": "social",
    "messaging": "communication",
    "communication": "communication",
    "chat": "communication",
    "lifestyle": "lifestyle",
    "food": "food_drink",
    "drink": "food_drink",
    "food drink": "food_drink",
    "recipe": "food_drink",
    "sports": "sports",
    "sport": "sports",
}

CATEGORY_SEED_LIBRARY = {
    "tools": [
        "calculator",
        "scientific calculator",
        "unit converter",
        "qr scanner",
        "file manager",
        "app manager",
        "phone cleaner",
        "password manager",
        "pdf scanner",
        "flashlight",
        "screen recorder",
        "wifi analyzer",
        "compass",
        "ruler",
        "speed test",
    ],
    "productivity": [
        "todo list",
        "notes app",
        "calendar planner",
        "habit tracker",
        "focus timer",
        "task manager",
        "document scanner",
        "pdf editor",
        "time tracker",
        "reminder app",
    ],
    "finance": [
        "loan calculator",
        "emi calculator",
        "savings calculator",
        "budget planner",
        "expense tracker",
        "currency converter",
        "investment tracker",
        "tax calculator",
        "mortgage calculator",
        "bill reminder",
    ],
    "health_fitness": [
        "bmi calculator",
        "calorie counter",
        "step counter",
        "workout tracker",
        "water reminder",
        "period tracker",
        "meal planner",
        "sleep tracker",
        "meditation timer",
        "weight tracker",
    ],
    "education": [
        "gpa calculator",
        "math solver",
        "language learning",
        "flashcards",
        "study planner",
        "dictionary",
        "translator",
        "exam preparation",
        "homework helper",
        "quiz maker",
    ],
    "business": [
        "invoice maker",
        "receipt scanner",
        "crm",
        "shift planner",
        "inventory manager",
        "expense report",
        "business card scanner",
        "team chat",
        "project manager",
        "payroll calculator",
    ],
    "photo_video": [
        "photo editor",
        "video editor",
        "collage maker",
        "background remover",
        "camera app",
        "beauty camera",
        "photo compressor",
        "video compressor",
        "slideshow maker",
        "reels editor",
    ],
    "entertainment": [
        "video streaming",
        "movie app",
        "tv shows",
        "series app",
        "live tv",
        "video player",
        "media player",
        "iptv player",
        "screen mirroring",
        "cast to tv",
    ],
    "music_audio": [
        "music player",
        "podcast player",
        "mp3 player",
        "music downloader",
        "audio recorder",
        "sound equalizer",
        "bass booster",
        "ringtone maker",
        "audiobook player",
        "music streaming",
    ],
    "games": [
        "puzzle game",
        "word game",
        "quiz game",
        "brain game",
        "arcade game",
        "strategy game",
        "casual game",
        "offline game",
        "card game",
        "board game",
    ],
    "news": [
        "news reader",
        "rss reader",
        "news aggregator",
        "breaking news",
        "news feed",
        "newspaper app",
        "headlines",
        "news alerts",
        "local news",
        "world news",
    ],
    "travel": [
        "flight tracker",
        "hotel booking",
        "trip planner",
        "travel guide",
        "maps navigation",
        "gps navigator",
        "train tracker",
        "bus tracker",
        "travel wallet",
        "currency converter",
    ],
    "shopping": [
        "price comparison",
        "coupon app",
        "deals finder",
        "online shopping",
        "barcode scanner",
        "wishlist app",
        "cashback app",
        "discount finder",
        "product scanner",
        "shopping list",
    ],
    "social": [
        "social network",
        "photo sharing",
        "video sharing",
        "dating app",
        "friend finder",
        "community app",
        "anonymous chat",
        "group chat",
        "live streaming",
        "story app",
    ],
    "communication": [
        "messaging app",
        "video call",
        "sms app",
        "voip call",
        "encrypted chat",
        "group messaging",
        "walkie talkie",
        "call recorder",
        "contacts backup",
        "email client",
    ],
    "lifestyle": [
        "journal app",
        "diary app",
        "daily planner",
        "mood tracker",
        "gratitude journal",
        "vision board",
        "quote app",
        "prayer app",
        "bible app",
        "horoscope app",
    ],
    "food_drink": [
        "recipe app",
        "meal planner",
        "calorie counter",
        "food tracker",
        "cooking app",
        "restaurant finder",
        "food delivery",
        "diet planner",
        "grocery list",
        "nutrition tracker",
    ],
    "sports": [
        "score tracker",
        "sports news",
        "live scores",
        "fitness tracker",
        "workout app",
        "running tracker",
        "cycling tracker",
        "team manager",
        "sports stats",
        "fantasy sports",
    ],
}


def available_keyword_categories() -> list[str]:
    return sorted(CATEGORY_SEED_LIBRARY)


def normalize_keyword_category(category: str) -> dict:
    """Normalize a category name into a supported local keyword taxonomy."""
    raw = (category or "").strip().lower()
    clean = re.sub(r"[^a-z0-9\s_-]+", " ", raw)
    clean = re.sub(r"[\s_-]+", " ", clean).strip()
    if not clean:
        return {"raw_category": category, "category": "", "matched": False, "warnings": []}

    category_id = CATEGORY_ALIASES.get(clean)
    warnings = []
    if not category_id:
        match = get_close_matches(clean, list(CATEGORY_ALIASES), n=1, cutoff=0.78)
        if match:
            category_id = CATEGORY_ALIASES[match[0]]
            warnings.append(f"Category '{clean}' was matched to '{category_id}'.")
        else:
            warnings.append(f"Category '{clean}' is not in the local taxonomy. Using free-form keywords only.")
            category_id = ""

    return {
        "raw_category": category,
        "category": category_id,
        "matched": bool(category_id),
        "warnings": warnings,
    }


def get_category_seed_keywords(category: str, limit: int = 12) -> dict:
    review = normalize_keyword_category(category)
    seeds = CATEGORY_SEED_LIBRARY.get(review["category"], [])[:limit]
    return {
        **review,
        "seeds": seeds,
        "source": "local_category_taxonomy",
        "legal_notes": "Local curated taxonomy only. No scraping or paid source is used.",
    }


def normalize_keyword_seed_input(raw_input: str, max_seeds: int = 12) -> dict:
    """Turn messy user input into safe, traceable seed keywords."""
    raw = (raw_input or "").strip()
    warnings = []
    corrections = []
    ignored_terms = []
    seeds = []

    if not raw:
        return {
            "raw_input": raw_input,
            "seeds": [],
            "corrections": [],
            "ignored_terms": [],
            "warnings": ["No keyword input was provided."],
            "quality_label": "invalid",
            "quality_score": 0,
        }

    chunks = [part.strip() for part in re.split(r"[,;\n|]+", raw) if part.strip()]
    if len(chunks) == 1 and len(raw.split()) > 6:
        warnings.append("Input looked like one long sentence. Add commas between seed topics for stronger results.")

    for chunk in chunks:
        normalized, chunk_corrections, chunk_ignored = _normalize_seed_chunk(chunk)
        corrections.extend(chunk_corrections)
        ignored_terms.extend(chunk_ignored)
        if normalized and normalized not in seeds:
            seeds.append(normalized)

    if len(seeds) > max_seeds:
        warnings.append(f"Input had {len(seeds)} seed topics. Only the first {max_seeds} were used to keep analysis reliable.")
        seeds = seeds[:max_seeds]

    if corrections:
        warnings.append("Some terms were normalized before scoring. Review corrections in the saved report.")
    if ignored_terms:
        warnings.append("Some unclear or filler terms were ignored instead of being scored as real keywords.")
    if not seeds:
        warnings.append("No reliable seed keywords could be built from the input.")

    quality_score = _input_quality_score(raw, seeds, corrections, ignored_terms)
    return {
        "raw_input": raw,
        "seeds": seeds,
        "corrections": corrections,
        "ignored_terms": ignored_terms,
        "warnings": warnings,
        "quality_label": _quality_label(quality_score),
        "quality_score": quality_score,
    }


def _normalize_seed_chunk(chunk: str) -> tuple[str, list[dict], list[str]]:
    original = chunk.strip()
    clean = re.sub(r"[^a-zA-Z0-9\s]+", " ", original.lower())
    words = [word for word in clean.split() if word]
    corrected_words = []
    corrections = []
    ignored = []

    for word in words:
        if word in NOISE_TERMS:
            ignored.append(word)
            continue

        fixed = COMMON_KEYWORD_FIXES.get(word)
        if not fixed:
            match = get_close_matches(word, DOMAIN_TERMS, n=1, cutoff=0.86)
            fixed = match[0] if match else word

        if fixed != word:
            corrections.append({"from": word, "to": fixed, "context": original})
        corrected_words.append(fixed)

    term = " ".join(corrected_words).strip()
    if not term:
        return "", corrections, ignored

    term = re.sub(r"\bapp\b", "", term).strip()
    term = re.sub(r"\s+", " ", term)
    if term in CALCULATOR_SEED_MAP:
        term = CALCULATOR_SEED_MAP[term]

    return term, corrections, ignored


def _input_quality_score(raw: str, seeds: list[str], corrections: list[dict], ignored_terms: list[str]) -> int:
    score = 100
    if not seeds:
        return 0
    if "," not in raw and len(raw.split()) > 6:
        score -= 25
    score -= min(len(corrections) * 5, 20)
    score -= min(len(ignored_terms) * 10, 30)
    if len(seeds) == 1:
        score -= 10
    return max(0, min(100, score))


def _quality_label(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    if score > 0:
        return "low"
    return "invalid"


def build_keyword_candidates(
    seeds: list[str],
    suggestions: list[str] | None = None,
    max_keywords: int = 30,
    seed_sources: dict[str, str] | None = None,
    live_support_map: dict[str, int] | None = None,
) -> list[dict]:
    """Build deduped keyword candidates from normalized seeds and optional approved-source suggestions."""
    candidates = []
    seen = set()

    def add(keyword: str, kind: str, count: int, source: str, seed_index: int, live_support: int = 0):
        clean = re.sub(r"\s+", " ", keyword.lower()).strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        candidates.append({
            "keyword": clean,
            "count": count,
            "type": kind,
            "source": source,
            "seed_index": seed_index,
            "intent_score": _keyword_intent_score(clean),
            "clarity_score": _keyword_clarity_score(clean),
            "live_support": max(0, int(live_support or 0)),
        })

    seed_sources = seed_sources or {}
    live_support_map = live_support_map or {}

    for index, seed in enumerate(seeds):
        source = seed_sources.get(seed, "normalized_input")
        kind = "category" if source == "category_seed" else "seed"
        count = 5 if source == "category_seed" else 6
        add(seed, kind, count, source, index, live_support=live_support_map.get(seed, 0))

    for suggestion in suggestions or []:
        if isinstance(suggestion, dict):
            add(
                suggestion.get("keyword", ""),
                suggestion.get("type", "suggestion"),
                int(suggestion.get("count", 4) or 4),
                suggestion.get("source", "approved_public_suggestion"),
                int(suggestion.get("seed_index", len(seeds)) or len(seeds)),
                live_support=int(suggestion.get("live_support", 0) or 0),
            )
        else:
            add(suggestion, "suggestion", 4, "approved_public_suggestion", len(seeds), live_support=1)

    for index, seed in enumerate(seeds):
        add(f"{seed} app", "variant", 2, "local_variant", index)
        add(f"free {seed}", "variant", 2, "local_variant", index)
        add(f"best {seed}", "variant", 2, "local_variant", index)
        add(f"{seed} android", "variant", 2, "local_variant", index)
        add(f"{seed} offline", "variant", 1, "local_variant", index)

    return candidates[:max_keywords]


def build_public_search_enrichment(
    queries: list[str],
    search_fn,
    *,
    lang: str = "en",
    country: str = "us",
    query_limit: int = 5,
    n_hits: int = 8,
    max_suggestions: int = 18,
) -> dict:
    """Use approved public search results to add live support and related keyword suggestions."""
    cleaned_queries = []
    for query in queries:
        clean = re.sub(r"\s+", " ", (query or "").strip().lower())
        if clean and clean not in cleaned_queries:
            cleaned_queries.append(clean)

    live_support_map: dict[str, int] = {}
    suggestions: list[dict] = []
    warnings: list[str] = []
    seen_suggestions: set[str] = set()
    seen_token_sets: set[frozenset[str]] = set()
    query_token_sets = [set(query.split()) for query in cleaned_queries]

    def add_suggestion(keyword: str, *, count: int, seed_index: int, live_support: int):
        clean = re.sub(r"\s+", " ", (keyword or "").strip().lower())
        if not clean or clean in seen_suggestions or clean in cleaned_queries:
            return
        tokens = clean.split()
        if len(tokens) > 4:
            return
        if len(set(tokens)) < len(tokens):
            return
        if clean in STOPWORDS or clean in NOISE_TERMS:
            return
        token_set = set(tokens)
        if any(token_set <= query_tokens for query_tokens in query_token_sets):
            return
        frozen = frozenset(token_set)
        if len(token_set) > 1 and frozen in seen_token_sets:
            return
        seen_suggestions.add(clean)
        seen_token_sets.add(frozen)
        suggestions.append(
            {
                "keyword": clean,
                "count": count,
                "type": "suggestion",
                "source": "approved_public_suggestion",
                "seed_index": seed_index,
                "live_support": live_support,
            }
        )

    for seed_index, query in enumerate(cleaned_queries[:query_limit]):
        try:
            results = search_fn(query, n_hits=n_hits, lang=lang, country=country) or []
        except Exception as exc:
            warnings.append(f"Public search enrichment failed for '{query}': {exc}")
            continue

        if not results:
            continue

        live_support_map[query] = min(len(results), 4)

        title_summary_text = " ".join(
            f"{item.get('title', '')} {item.get('summary', '')}"
            for item in results[:n_hits]
        )
        extracted = extract_keywords_from_text(title_summary_text, top_n=16)
        for item in extracted:
            keyword = str(item.get("keyword", "")).strip().lower()
            count = int(item.get("count", 1) or 1)
            kind = item.get("type", "")
            if count < 2 and kind != "single":
                continue
            if kind == "single" and count < 3:
                continue
            if len(keyword.split()) == 1 and keyword not in DOMAIN_TERMS:
                continue
            add_suggestion(keyword, count=min(max(count, 3), 6), seed_index=seed_index, live_support=min(count, 3))

    return {
        "live_support_map": live_support_map,
        "suggestions": suggestions[:max_suggestions],
        "warnings": warnings,
        "queries_used": cleaned_queries[:query_limit],
    }


def _keyword_intent_score(keyword: str) -> int:
    score = 0
    words = keyword.split()
    # Multi-word = more specific intent, less competition
    if len(words) >= 2:
        score += 10
    if len(words) >= 3:
        score += 5
    # Action/modifier words that signal user intent regardless of category
    action_modifiers = {"free", "offline", "best", "pro", "lite", "fast", "simple", "easy", "smart", "quick"}
    if any(mod in words for mod in action_modifiers):
        score += 8
    # Platform specificity
    if "android" in words:
        score += 4
    return min(score, 25)


def _keyword_clarity_score(keyword: str) -> int:
    words = keyword.split()
    if 2 <= len(words) <= 4:
        return 15
    if len(words) == 1:
        return 8
    return 5


def extract_keywords_from_text(text: str, min_len: int = 3, top_n: int = 50) -> list:
    """Extract meaningful keywords from any text via frequency analysis."""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    words = [w for w in text.split() if len(w) >= min_len and w not in STOPWORDS]

    # Single words
    single = Counter(words)

    # Bigrams (2-word phrases)
    bigrams = Counter()
    for i in range(len(words) - 1):
        bg = f"{words[i]} {words[i+1]}"
        if words[i] not in STOPWORDS and words[i+1] not in STOPWORDS:
            bigrams[bg] += 1

    # Trigrams (3-word phrases)
    trigrams = Counter()
    for i in range(len(words) - 2):
        tg = f"{words[i]} {words[i+1]} {words[i+2]}"
        if not any(w in STOPWORDS for w in [words[i], words[i+2]]):
            trigrams[tg] += 1

    combined = []
    for word, count in single.most_common(top_n):
        combined.append({"keyword": word, "count": count, "type": "single"})
    for phrase, count in bigrams.most_common(20):
        if count >= 2:
            combined.append({"keyword": phrase, "count": count, "type": "bigram"})
    for phrase, count in trigrams.most_common(10):
        if count >= 2:
            combined.append({"keyword": phrase, "count": count, "type": "trigram"})

    return combined


def mine_review_keywords(reviews: list) -> dict:
    """
    NLP mine real user reviews to discover:
    - What users love (5-star reviews -> feature keywords)
    - What users hate (1-2 star reviews -> pain point keywords)
    - How users describe the app (natural search language)
    """
    positive_texts = []
    negative_texts = []
    all_texts = []

    for r in reviews:
        text = r.get("text", "")
        score = r.get("score", 3)
        all_texts.append(text)
        if score >= 4:
            positive_texts.append(text)
        elif score <= 2:
            negative_texts.append(text)

    return {
        "positive_keywords": extract_keywords_from_text(" ".join(positive_texts), top_n=30),
        "negative_keywords": extract_keywords_from_text(" ".join(negative_texts), top_n=20),
        "all_keywords": extract_keywords_from_text(" ".join(all_texts), top_n=50),
        "review_count": len(reviews),
        "positive_count": len(positive_texts),
        "negative_count": len(negative_texts),
    }


def get_google_trends(keywords: list, timeframe: str = "today 3-m") -> dict:
    """
    Fetch REAL trend data from Google Trends via pytrends.
    Returns interest over time scores (0-100).
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {"error": "pytrends not installed. Run: pip install pytrends", "data": {}}

    if not keywords:
        return {"data": {}, "related": []}

    # Pytrends max 5 keywords per request
    chunks = [keywords[i:i+5] for i in range(0, min(len(keywords), 15), 5)]
    trend_scores = {}
    related_queries = []

    pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))

    for chunk in chunks[:3]:
        try:
            pytrends.build_payload(chunk, cat=0, timeframe=timeframe, geo="", gprop="")
            time.sleep(1)

            # Interest over time
            iot = pytrends.interest_over_time()
            if not iot.empty:
                for kw in chunk:
                    if kw in iot.columns:
                        avg = int(iot[kw].mean())
                        timeline = iot[kw].tolist()
                        trend_scores[kw] = {
                            "avg_interest": avg,
                            "peak": int(iot[kw].max()),
                            "recent": int(iot[kw].iloc[-1]) if len(iot) > 0 else 0,
                            "trend": _calc_trend_direction(timeline),
                            "timeline": [int(v) for v in timeline[-30:]],  # last 30 for sparkline
                        }

            # Related queries
            try:
                related = pytrends.related_queries()
                for kw in chunk:
                    if kw in related and related[kw]["top"] is not None:
                        tops = related[kw]["top"].head(5)
                        for _, row in tops.iterrows():
                            q = row.get("query", "")
                            if q and q not in related_queries:
                                related_queries.append(q)
            except Exception:
                pass

            time.sleep(1.5)

        except Exception as e:
            for kw in chunk:
                trend_scores[kw] = {"error": str(e)}

    return {
        "data": trend_scores,
        "related_queries": related_queries[:20],
        "timeframe": timeframe,
        "fetched_at": datetime.now().isoformat(),
    }


def _calc_trend_direction(values: list) -> str:
    """Determine if trend is rising, falling, or stable."""
    if len(values) < 4:
        return "stable"
    first_half = sum(values[:len(values)//2]) / max(len(values)//2, 1)
    second_half = sum(values[len(values)//2:]) / max(len(values) - len(values)//2, 1)
    diff = second_half - first_half
    if diff > 10:
        return "rising"
    elif diff < -10:
        return "falling"
    return "stable"


def find_keyword_gaps(your_app: dict, competitors: list) -> dict:
    """
    Find keywords (single words + bigrams + trigrams) competitors use that you don't.
    Phrases are higher-value gaps — users search 'file manager offline', not just 'file'.
    """
    def get_terms(app_data: dict) -> set:
        text = f"{app_data.get('title','')} {app_data.get('summary','')} {app_data.get('description','')}"
        text = text.lower()
        text = re.sub(r"[^a-z\s]", " ", text)
        words = [w for w in text.split() if (len(w) >= 3 or w in SHORT_KEEP) and w not in STOPWORDS]

        terms: set[str] = set(words)

        # Bigrams — 2-word phrases that appear consecutively
        for i in range(len(words) - 1):
            if words[i] not in STOPWORDS and words[i+1] not in STOPWORDS:
                terms.add(f"{words[i]} {words[i+1]}")

        # Trigrams — only add if all 3 words are meaningful
        for i in range(len(words) - 2):
            if not any(w in STOPWORDS for w in words[i:i+3]):
                terms.add(f"{words[i]} {words[i+1]} {words[i+2]}")

        return terms

    def term_type(term: str) -> str:
        n = len(term.split())
        if n == 1: return "word"
        if n == 2: return "phrase"
        return "phrase (3w)"

    your_terms = get_terms(your_app)
    competitor_term_counts: Counter = Counter()

    for comp in competitors:
        comp_terms = get_terms(comp)
        for t in comp_terms:
            competitor_term_counts[t] += 1

    # Terms used by 2+ competitors but not by you — phrases prioritized first
    gaps = []
    for term, count in competitor_term_counts.most_common(200):
        if term not in your_terms and count >= 2:
            gaps.append({
                "keyword": term,
                "used_by_competitors": count,
                "type": term_type(term),
            })

    # Sort: phrases first (higher search intent), then by competitor count
    gaps.sort(key=lambda g: (0 if g["type"] != "word" else 1, -g["used_by_competitors"]))

    return {
        "your_keyword_count": len(your_terms),
        "gaps_found": len(gaps),
        "top_gaps": gaps[:40],
        "your_unique_keywords": list(
            your_terms - set(competitor_term_counts.keys())
        )[:20],
    }


def _priority_label_ascii(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def score_keywords(keywords: list, trend_data: dict) -> list:
    """
    Score and rank keywords combining frequency + trend momentum.
    Returns sorted list with composite scores.
    """
    scored = []
    trend_info = trend_data.get("data", {})

    for kw_item in keywords:
        kw = kw_item if isinstance(kw_item, str) else kw_item.get("keyword", "")
        freq = kw_item.get("count", 1) if isinstance(kw_item, dict) else 1
        kw_type = kw_item.get("type", "single") if isinstance(kw_item, dict) else "single"
        source = kw_item.get("source", "unknown") if isinstance(kw_item, dict) else "unknown"
        seed_index = kw_item.get("seed_index", 9999) if isinstance(kw_item, dict) else 9999
        intent_score = kw_item.get("intent_score", _keyword_intent_score(kw)) if isinstance(kw_item, dict) else _keyword_intent_score(kw)
        clarity_score = kw_item.get("clarity_score", _keyword_clarity_score(kw)) if isinstance(kw_item, dict) else _keyword_clarity_score(kw)
        live_support = kw_item.get("live_support", 0) if isinstance(kw_item, dict) else 0

        # Trend score (0-100)
        trend = trend_info.get(kw, {})
        trend_score = trend.get("avg_interest", 0) if isinstance(trend, dict) else 0

        # Word count bonus (long-tail = less competition)
        words = kw.split()
        longtail_bonus = min(len(words) * 5, 20)

        source_bonus = _source_weight_bonus(source)
        live_support_bonus = _live_support_bonus(source, live_support)

        # Composite score. Trend data is optional because legal policy may disable public trend access.
        composite = (freq * 4) + (trend_score * 0.45) + longtail_bonus + intent_score + clarity_score + source_bonus + live_support_bonus
        capped_composite = min(composite, 100)
        confidence = _keyword_confidence_label(trend_score, source, clarity_score, live_support)

        scored.append({
            "keyword": kw,
            "type": kw_type,
            "frequency": freq,
            "source": source,
            "seed_index": seed_index,
            "live_support": int(live_support),
            "trend_interest": trend_score,
            "trend_direction": trend.get("trend", "n/a (disabled by policy)") if isinstance(trend, dict) else "n/a (disabled by policy)",
            "longtail_bonus": longtail_bonus,
            "intent_score": intent_score,
            "clarity_score": clarity_score,
            "source_bonus": source_bonus,
            "live_support_bonus": live_support_bonus,
            "composite_score": round(capped_composite, 1),
            "priority": _priority_label_ascii(capped_composite),
            "confidence": confidence,
        })

    type_rank = {"seed": 0, "category": 1, "suggestion": 2, "variant": 3}
    return sorted(
        scored,
        key=lambda x: (
            1 if x.get("type") == "variant" else 0,
            -x["composite_score"],
            type_rank.get(x.get("type", ""), 9),
            x.get("seed_index", 9999),
            x["keyword"],
        ),
    )


def _keyword_confidence_label(trend_score: int, source: str, clarity_score: int, live_support: int = 0) -> str:
    if (trend_score > 0 or live_support >= 2) and source != "unknown" and clarity_score >= 10:
        return "high"
    if source in {"category_seed", "approved_public_suggestion"}:
        return "medium"
    if source != "unknown" and clarity_score >= 10:
        return "medium"
    return "low"


def _source_weight_bonus(source: str) -> int:
    if source == "normalized_input":
        return 28
    if source == "category_seed":
        return 25
    if source == "approved_public_suggestion":
        return 18
    if source == "local_variant":
        return 5
    return 0


def _live_support_bonus(source: str, live_support: int) -> int:
    support = max(0, int(live_support or 0))
    if source == "category_seed":
        return min(support * 4, 12)
    return min(support * 8, 24)
