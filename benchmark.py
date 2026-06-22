import time
from typing import Any

def original(title, summary, description, keywords):
    keyword_hits = {keyword: keyword.lower() in f"{title} {summary} {description}".lower() for keyword in keywords}
    title_score = min(100, len(title) * 2 + sum(keyword.lower() in title.lower() for keyword in keywords) * 15)
    summary_score = min(100, len(summary) + sum(keyword.lower() in summary.lower() for keyword in keywords) * 12)
    long_score = min(100, len(description) / 40 + sum(keyword_hits.values()) * 10)
    return keyword_hits, title_score, summary_score, long_score

def optimized(title, summary, description, keywords):
    title_lower = title.lower()
    summary_lower = summary.lower()
    combined_lower = f"{title_lower} {summary_lower} {description.lower()}"

    lower_keywords = [keyword.lower() for keyword in keywords]

    keyword_hits = {keyword: lower_kw in combined_lower for keyword, lower_kw in zip(keywords, lower_keywords)}
    title_score = min(100, len(title) * 2 + sum(lower_kw in title_lower for lower_kw in lower_keywords) * 15)
    summary_score = min(100, len(summary) + sum(lower_kw in summary_lower for lower_kw in lower_keywords) * 12)
    long_score = min(100, len(description) / 40 + sum(keyword_hits.values()) * 10)
    return keyword_hits, title_score, summary_score, long_score

title = "This is a Great Title for an App"
summary = "This is a summary of the app. It is very cool and awesome."
description = "This is a very long description. " * 100
keywords = ["App", "Cool", "Awesome", "Great", "Test", "NotThere", "AlsoNotThere", "Very", "Long", "Description"] * 10

assert original(title, summary, description, keywords) == optimized(title, summary, description, keywords)

import timeit
print("Original:", timeit.timeit(lambda: original(title, summary, description, keywords), number=10000))
print("Optimized:", timeit.timeit(lambda: optimized(title, summary, description, keywords), number=10000))
