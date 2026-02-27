# Analysis Algorithms

Detailed algorithms for sentiment, theme extraction, and trend detection.

## Sentiment Scoring Algorithm

```python
def score_sentiment(text: str) -> tuple[str, str]:
    """
    Returns (category, intensity)
    category: positive, negative, neutral, mixed
    intensity: strong, moderate, mild
    """

    # Keyword dictionaries
    positive_strong = ["love", "amazing", "perfect", "brilliant", "excellent"]
    positive_moderate = ["good", "helpful", "useful", "nice", "better"]
    positive_mild = ["ok", "fine", "works", "decent"]

    negative_strong = ["hate", "terrible", "broken", "unusable", "awful"]
    negative_moderate = ["frustrating", "confusing", "slow", "annoying", "difficult"]
    negative_mild = ["minor", "small issue", "could be better"]

    # Count occurrences (case-insensitive)
    text_lower = text.lower()

    pos_strong = sum(1 for word in positive_strong if word in text_lower)
    pos_moderate = sum(1 for word in positive_moderate if word in text_lower)
    pos_mild = sum(1 for word in positive_mild if word in text_lower)

    neg_strong = sum(1 for word in negative_strong if word in text_lower)
    neg_moderate = sum(1 for word in negative_moderate if word in text_lower)
    neg_mild = sum(1 for word in negative_mild if word in text_lower)

    # Score calculation
    pos_score = (pos_strong * 3) + (pos_moderate * 2) + (pos_mild * 1)
    neg_score = (neg_strong * 3) + (neg_moderate * 2) + (neg_mild * 1)

    # Intensity modifiers
    if "!!!" in text or "???" in text:
        if pos_score > neg_score:
            pos_score *= 1.5
        else:
            neg_score *= 1.5

    # CAPS detection
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.3:
        neg_score *= 1.3  # CAPS usually indicates frustration

    # Determine category
    if pos_score > neg_score * 2:
        category = "positive"
        intensity = "strong" if pos_strong > 0 else "moderate" if pos_moderate > 0 else "mild"
    elif neg_score > pos_score * 2:
        category = "negative"
        intensity = "strong" if neg_strong > 0 else "moderate" if neg_moderate > 0 else "mild"
    elif abs(pos_score - neg_score) < 2:
        category = "mixed"
        intensity = "moderate"
    else:
        category = "neutral"
        intensity = "mild"

    return category, intensity
```

## Theme Extraction Algorithm

```python
def extract_themes(feedback_items: list[dict]) -> list[dict]:
    """
    Cluster feedback into themes using keyword frequency and co-occurrence.
    Returns list of themes sorted by priority.
    """

    # 1. Keyword extraction
    keywords = {}
    for item in feedback_items:
        words = extract_keywords(item['content'])
        for word in words:
            keywords[word] = keywords.get(word, 0) + 1

    # 2. Identify theme clusters
    # Keywords that frequently appear together form themes
    themes = cluster_by_cooccurrence(keywords, feedback_items)

    # 3. Score themes by priority
    for theme in themes:
        theme['priority'] = calculate_priority(
            frequency=theme['count'],
            severity=theme['avg_severity'],
            urgency=theme['avg_urgency'],
            total=len(feedback_items)
        )

    # 4. Sort by priority
    return sorted(themes, key=lambda t: t['priority'], reverse=True)

def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords, excluding stopwords."""
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to"}
    words = text.lower().split()
    return [w for w in words if len(w) > 3 and w not in stopwords]

def cluster_by_cooccurrence(keywords: dict, items: list) -> list[dict]:
    """Find keywords that frequently appear together."""
    # Use Jaccard similarity for clustering
    # Keywords with >50% co-occurrence likely form a theme
    pass  # Implementation details

def calculate_priority(frequency: int, severity: float, urgency: float, total: int) -> float:
    """
    Priority = (Frequency_Ratio × Severity × Urgency)

    frequency_ratio = frequency / total
    severity = 1-5 (derived from sentiment intensity and keywords)
    urgency = 1-5 (derived from recency and churn signals)
    """
    freq_ratio = frequency / max(total, 1)
    return freq_ratio * severity * urgency
```

## Trend Detection Algorithm

```python
def detect_trends(theme: str, timeframes: list[str]) -> dict:
    """
    Detect if theme is emerging, growing, stable, or declining.

    Args:
        theme: Theme keyword(s)
        timeframes: List of time periods (e.g., ["2025-12", "2026-01"])

    Returns:
        {
            "trend": "GROWING" | "STABLE" | "DECLINING" | "EMERGING",
            "change": "+45%",
            "baseline": 10,
            "current": 15
        }
    """

    # Count mentions per timeframe
    counts = []
    for period in timeframes:
        count = count_theme_mentions(theme, period)
        counts.append(count)

    # Detect pattern
    if len(counts) < 2:
        return {"trend": "INSUFFICIENT_DATA"}

    baseline = counts[-2]  # Previous period
    current = counts[-1]   # Current period

    # Calculate change
    if baseline == 0:
        if current > 5:
            return {
                "trend": "EMERGING",
                "change": "new",
                "baseline": 0,
                "current": current
            }
        else:
            return {"trend": "INSUFFICIENT_DATA"}

    change_pct = ((current - baseline) / baseline) * 100

    if change_pct > 50:
        trend = "GROWING"
    elif change_pct < -30:
        trend = "DECLINING"
    elif abs(change_pct) <= 20:
        trend = "STABLE"
    else:
        trend = "STABLE"

    return {
        "trend": trend,
        "change": f"{change_pct:+.0f}%",
        "baseline": baseline,
        "current": current
    }
```

## Segment Comparison Algorithm

```python
def compare_segments(theme: str, segments: list[str]) -> dict:
    """
    Compare how different customer segments feel about a theme.

    Returns:
        {
            "enterprise": {"sentiment": "negative", "count": 25},
            "smb": {"sentiment": "positive", "count": 12},
            "insights": "Enterprise users struggling with feature X"
        }
    """

    results = {}
    for segment in segments:
        feedback = filter_by_segment(theme, segment)

        sentiment_scores = [score_sentiment(f['content']) for f in feedback]
        avg_sentiment = aggregate_sentiment(sentiment_scores)

        results[segment] = {
            "sentiment": avg_sentiment,
            "count": len(feedback),
            "top_keywords": extract_top_keywords(feedback, limit=3)
        }

    # Generate insights from differences
    insights = generate_segment_insights(results)

    return {**results, "insights": insights}
```

## Implementation Notes

For actual implementation, prefer:
- Lightweight text processing (no heavy NLP libraries)
- Regex-based keyword extraction
- Simple frequency counting
- File-based storage (no database required)

## Performance

- Target: <5s for 1000 feedback items
- Cache theme extractions for 1 hour
- Incremental updates (don't reprocess all feedback)
