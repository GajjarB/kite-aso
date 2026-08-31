"""
ASO Metadata Analyzer
- Scores title, short description, long description
- Enforces real Google Play character limits
- Checks keyword placement and density
- Gives actionable fix recommendations
"""

import re
from collections import Counter

# Google Play Store real limits
LIMITS = {
    "title": 30,
    "short_description": 80,
    "long_description": 4000,
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "this", "that", "are",
    "was", "were", "be", "been", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "not", "no",
}


def analyze_metadata(title: str, short_desc: str, long_desc: str) -> dict:
    """Full ASO metadata analysis with scores and fixes."""
    title_result = _analyze_title(title)
    short_result = _analyze_short_desc(short_desc)
    long_result = _analyze_long_desc(long_desc)
    overlap = _check_keyword_overlap(title, short_desc, long_desc)
    overall = _overall_score(title_result, short_result, long_result)

    return {
        "overall_score": overall["score"],
        "grade": overall["grade"],
        "title": title_result,
        "short_description": short_result,
        "long_description": long_result,
        "keyword_strategy": overlap,
        "quick_wins": _quick_wins(title_result, short_result, long_result, overlap),
    }


def _analyze_title(title: str) -> dict:
    length = len(title)
    limit = LIMITS["title"]
    words = title.split()
    issues = []
    suggestions = []
    score = 100

    # Length check
    if length > limit:
        issues.append(f"Title too long: {length}/{limit} chars. Google WILL truncate.")
        score -= 30
    elif length < 15:
        issues.append(f"Title too short: {length} chars. Missing keyword opportunities.")
        suggestions.append("Expand to 20-30 chars. Add primary keyword.")
        score -= 20
    else:
        suggestions.append(f"✓ Good length: {length}/{limit} chars")

    # Keyword in title (most important ranking factor)
    if "|" in title or "-" in title or ":" in title:
        suggestions.append("✓ Using separator — good for branding + keyword combo")
    else:
        suggestions.append("Consider 'AppName - Primary Keyword' format for extra keyword.")

    # Special characters
    if re.search(r"[!@#$%^&*()+=\[\]{};'\"<>?/\\]", title):
        issues.append("Special characters can hurt rankings. Remove them.")
        score -= 10

    # ALL CAPS words
    caps_words = [w for w in words if w.isupper() and len(w) > 2]
    if caps_words:
        issues.append(f"Avoid ALL CAPS words: {caps_words}")
        score -= 5

    return {
        "text": title,
        "length": length,
        "limit": limit,
        "chars_remaining": max(0, limit - length),
        "score": max(0, score),
        "issues": issues,
        "suggestions": suggestions,
    }


def _analyze_short_desc(text: str) -> dict:
    length = len(text)
    limit = LIMITS["short_description"]
    issues = []
    suggestions = []
    score = 100

    if length > limit:
        issues.append(f"Too long: {length}/{limit} chars. Will be cut off.")
        score -= 25
    elif length < 40:
        issues.append(f"Too short: {length} chars. Wasted opportunity.")
        suggestions.append("Use all 80 chars. Pack with keywords + value prop.")
        score -= 20

    # CTA check
    cta_words = ["download", "try", "start", "get", "install", "join", "free"]
    has_cta = any(w in text.lower() for w in cta_words)
    if not has_cta:
        suggestions.append("Add a call-to-action word (Download, Try, Get started).")
        score -= 10
    else:
        suggestions.append("✓ Has call-to-action")

    # Emoji usage
    emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FAFF]', text))
    if emoji_count == 0:
        suggestions.append("Consider 1-2 emojis to improve click-through rate.")
    elif emoji_count > 4:
        issues.append("Too many emojis can look spammy.")
        score -= 5
    else:
        suggestions.append(f"✓ Good emoji usage ({emoji_count})")

    # Keyword density (min 3 chars to catch "qr", "ai", "pdf" etc. via STOPWORDS exclusion)
    words = [w for w_raw in re.findall(r'\b[a-zA-Z]{3,}\b', text) if (w := w_raw.lower()) not in STOPWORDS]
    if len(words) < 5:
        issues.append("Add more meaningful keywords.")
        score -= 15

    return {
        "text": text,
        "length": length,
        "limit": limit,
        "chars_remaining": max(0, limit - length),
        "score": max(0, score),
        "issues": issues,
        "suggestions": suggestions,
    }


def _above_fold_analysis(text: str) -> dict:
    """
    Google Play shows first 80 chars of long desc before 'Read more'.
    This is prime real estate — must hook + primary keyword.
    """
    fold = text[:80]
    length = len(fold)
    meaningful = [
        w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', fold)
        if w.lower() not in STOPWORDS
    ]
    issues = []
    suggestions = []
    score = 100

    if length < 50:
        issues.append(
            f"Above-fold only {length}/80 chars. Users see this BEFORE 'Read more' — fill it."
        )
        score -= 40
    elif length < 70:
        issues.append(f"Above-fold weak: {length}/80 chars. Add primary keyword in first 80.")
        score -= 15
    else:
        suggestions.append(f"OK Above-fold uses {length}/80 chars")

    if len(meaningful) < 3:
        issues.append("First 80 chars lacks keywords. Add your top keyword immediately.")
        score -= 20
    elif len(meaningful) >= 5:
        suggestions.append(f"OK First 80 chars has {len(meaningful)} meaningful keywords")

    return {
        "text": fold,
        "length": length,
        "keyword_count": len(meaningful),
        "score": max(0, score),
        "issues": issues,
        "suggestions": suggestions,
    }


def _keyword_density(text: str) -> dict:
    """
    Keyword density: frequency per 1000 chars, stuffing detection (>3% of words).
    """
    words = [
        w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text)
        if w.lower() not in STOPWORDS
    ]
    total_words = max(len(words), 1)
    total_chars = max(len(text), 1)
    freq = Counter(words)
    stuffing_warnings = []

    top_density = []
    for word, count in freq.most_common(10):
        pct = count / total_words * 100
        per_1000 = count / total_chars * 1000
        if pct > 3.0:
            stuffing_warnings.append(
                f"'{word}' appears {count}x ({pct:.1f}% of words) — stuffing risk"
            )
        top_density.append({
            "keyword": word,
            "count": count,
            "pct": round(pct, 1),
            "per_1000_chars": round(per_1000, 2),
            "stuffing_risk": pct > 3.0,
        })

    return {
        "total_words": total_words,
        "total_chars": total_chars,
        "top_keywords": top_density,
        "stuffing_warnings": stuffing_warnings,
    }


def _readability_proxy(text: str) -> dict:
    """
    Simple readability: avg words per sentence.
    Target 12-20 words/sentence — users skim Play Store listings.
    """
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10]
    if not sentences:
        return {
            "avg_words_per_sentence": 0, "sentence_count": 0,
            "grade": "N/A", "score": 50,
        }
    avg = sum(len(s.split()) for s in sentences) / len(sentences)
    if 10 <= avg <= 20:
        grade, score = "Excellent", 100
    elif 8 <= avg <= 25:
        grade, score = "Good", 80
    elif avg < 8:
        grade, score = "Fragmented", 60
    else:
        grade, score = "Too dense" if avg <= 35 else "Very dense", 50
    return {
        "avg_words_per_sentence": round(avg, 1),
        "sentence_count": len(sentences),
        "grade": grade,
        "score": score,
    }


def _analyze_long_desc(text: str) -> dict:
    length = len(text)
    limit = LIMITS["long_description"]
    issues = []
    suggestions = []
    score = 100

    # Length
    if length < 500:
        issues.append(f"Too short: {length} chars. Ideal is 2000-4000.")
        score -= 35
    elif length < 1500:
        issues.append(f"Moderate length: {length} chars. Aim for 2000+.")
        score -= 15
    elif length > limit:
        issues.append(f"Exceeds limit: {length}/{limit} chars.")
        score -= 20
    else:
        suggestions.append(f"✓ Good length: {length} chars")

    # Above-fold (Google shows first 80 chars before "read more")
    above_fold = _above_fold_analysis(text)
    issues.extend(above_fold["issues"])
    suggestions.extend(above_fold["suggestions"])
    if above_fold["score"] < 80:
        score -= int((100 - above_fold["score"]) * 0.25)

    # Structure checks
    has_bullets = any(c in text for c in ("•", "●", "★", "✓", "◆", "-"))
    if not has_bullets:
        suggestions.append("Add bullet points (•) for scanability. Most users skim.")
        score -= 10
    else:
        suggestions.append("✓ Has bullet points / visual structure")

    # Keyword frequency + density
    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text) if w.lower() not in STOPWORDS]
    word_freq = Counter(words).most_common(10)
    top_keywords = [w for w, _ in word_freq]
    total_words = max(len(words), 1)

    density = _keyword_density(text)
    for warning in density["stuffing_warnings"]:
        issues.append(warning)
        score -= 12

    # Readability
    readability = _readability_proxy(text)
    if readability["score"] < 70:
        suggestions.append(
            f"Readability: avg {readability['avg_words_per_sentence']} words/sentence ({readability['grade']}). "
            "Aim for 12-20 words/sentence."
        )

    # Feature mentions
    feature_words = ["feature", "privacy", "secure", "offline", "sync", "fast", "free", "easy"]
    found_features = [w for w in feature_words if w in text.lower()]
    if len(found_features) < 3:
        suggestions.append("Mention more features explicitly: privacy, offline, sync, speed.")
        score -= 5

    return {
        "length": length,
        "limit": limit,
        "chars_remaining": max(0, limit - length),
        "score": max(0, score),
        "issues": issues,
        "suggestions": suggestions,
        "top_keywords_found": top_keywords,
        "word_count": total_words,
        "above_fold": above_fold,
        "density": density,
        "readability": readability,
    }


def _check_keyword_overlap(title: str, short: str, long: str) -> dict:
    """Check if primary keywords flow from title → short → long description."""
    def tokenize(t):
        return {w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', t) if w.lower() not in STOPWORDS}

    title_kws = tokenize(title)
    short_kws = tokenize(short)
    long_kws = tokenize(long)

    in_title_and_short = title_kws & short_kws
    in_title_not_short = title_kws - short_kws
    in_short_not_long = short_kws - long_kws
    in_all_three = title_kws & short_kws & long_kws

    return {
        "title_keywords": list(title_kws),
        "consistent_across_all": list(in_all_three),
        "title_keywords_missing_from_short": list(in_title_not_short),
        "short_keywords_missing_from_long": list(in_short_not_long),
        "consistency_score": round(len(in_all_three) / max(len(title_kws), 1) * 100),
        "recommendation": (
            "✓ Good keyword consistency" if len(in_all_three) >= 2
            else "⚠ Add title keywords to your short description and long description"
        ),
    }


def _overall_score(title_r, short_r, long_r) -> dict:
    # Weighted: title 50% (most important ranking factor), short desc 20%, long desc 30%
    score = (
        title_r["score"] * 0.50 +
        short_r["score"] * 0.20 +
        long_r["score"] * 0.30
    )
    score = round(score)
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "F"
    return {"score": score, "grade": grade}


def _quick_wins(title_r, short_r, long_r, overlap: dict) -> list:
    """Return top 5 highest-impact fixes sorted by impact."""
    wins = []

    if title_r["score"] < 80:
        wins.append({"impact": "HIGH", "area": "Title", "fix": title_r["issues"][0] if title_r["issues"] else "Improve title keywords"})
    if short_r["score"] < 80:
        wins.append({"impact": "HIGH", "area": "Short Desc", "fix": short_r["issues"][0] if short_r["issues"] else "Expand short description"})
    if long_r["score"] < 70:
        wins.append({"impact": "MEDIUM", "area": "Long Desc", "fix": long_r["issues"][0] if long_r["issues"] else "Expand long description"})
    if overlap.get("consistency_score", 100) < 50:
        wins.append({"impact": "MEDIUM", "area": "Keyword Strategy", "fix": overlap.get("recommendation", "Align keywords across title, short, and long description")})
    if not wins:
        wins.append({"impact": "LOW", "area": "Overall", "fix": "Metadata looks solid. Focus on review acquisition."})

    return wins[:5]


def compare_metadata(your_app: dict, competitors: list) -> dict:
    """Side-by-side metadata comparison with your app vs competitors."""
    rows = []

    def score_app(a):
        return _overall_score(
            _analyze_title(a.get("title", "")),
            _analyze_short_desc(a.get("summary", "")),
            _analyze_long_desc(a.get("description", "")),
        )

    your_score = score_app(your_app)
    rows.append({
        "app": your_app.get("title", "Your App"),
        "package": your_app.get("package_id", ""),
        "title_len": len(your_app.get("title", "")),
        "short_len": len(your_app.get("summary", "")),
        "long_len": len(your_app.get("description", "")),
        "score": your_score["score"],
        "grade": your_score["grade"],
        "rating": your_app.get("score", 0),
        "installs": your_app.get("installs", ""),
        "is_you": True,
    })

    for comp in competitors:
        cs = score_app(comp)
        rows.append({
            "app": comp.get("title", "Competitor"),
            "package": comp.get("package_id", ""),
            "title_len": len(comp.get("title", "")),
            "short_len": len(comp.get("summary", "")),
            "long_len": len(comp.get("description", "")),
            "score": cs["score"],
            "grade": cs["grade"],
            "rating": comp.get("score", 0),
            "installs": comp.get("installs", ""),
            "is_you": False,
        })

    rows.sort(key=lambda x: x["score"], reverse=True)
    return {"comparison": rows}
