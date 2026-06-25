"""SEO scoring, keyword density checks, and lightweight optimization."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


WORD_PATTERN = re.compile(r"\b[\w'-]+\b", re.IGNORECASE)


@dataclass(slots=True)
class SEOAnalysis:
    """Structured SEO analysis result."""

    score: int
    optimized_content: str
    keyword_density: dict[str, float]
    readability_score: float

    def as_dict(self) -> dict[str, object]:
        """Return a dictionary representation.

        Returns:
            SEO result dictionary.
        """

        return {
            "score": self.score,
            "optimized_content": self.optimized_content,
            "keyword_density": self.keyword_density,
            "readability_score": self.readability_score,
        }


def optimize(content: str, keywords: list[str]) -> dict[str, object]:
    """Optimize content for keyword presence, density, and readability.

    Args:
        content: Draft content.
        keywords: Target SEO keywords.

    Returns:
        Dictionary containing score, optimized content, keyword density, and readability.
    """

    normalized_keywords = [keyword.strip().lower() for keyword in keywords if keyword.strip()]
    optimized_content = content.strip()
    for keyword in normalized_keywords:
        if keyword not in optimized_content.lower():
            optimized_content = _inject_keyword(optimized_content, keyword)

    density = _keyword_density(optimized_content, normalized_keywords)
    readability = _flesch_reading_ease(optimized_content)
    heading_score = 20 if _has_heading_structure(optimized_content) else 0
    presence_score = _presence_score(optimized_content, normalized_keywords)
    density_score = _density_score(density)
    readability_score = 20 if readability >= 50 else 10 if readability >= 30 else 0
    total_score = min(100, presence_score + density_score + heading_score + readability_score)
    return SEOAnalysis(
        score=total_score,
        optimized_content=optimized_content,
        keyword_density=density,
        readability_score=round(readability, 2),
    ).as_dict()


def _inject_keyword(content: str, keyword: str) -> str:
    """Inject a missing keyword using a short contextual sentence.

    Args:
        content: Content to update.
        keyword: Keyword to inject.

    Returns:
        Content with keyword included.
    """

    if not content:
        return f"# {keyword.title()}\n\nThis guide explains {keyword} with practical context."
    insertion = f"\n\nA practical strategy should also account for {keyword} across planning and execution."
    return f"{content.rstrip()}{insertion}"


def _keyword_density(content: str, keywords: list[str]) -> dict[str, float]:
    """Calculate keyword density as a percentage of total words.

    Args:
        content: Content to analyze.
        keywords: Target keywords.

    Returns:
        Keyword density percentages.
    """

    words = [word.lower() for word in WORD_PATTERN.findall(content)]
    total_words = max(1, len(words))
    counts = Counter(words)
    return {
        keyword: round(sum(counts[token] for token in keyword.split()) / total_words * 100, 2)
        for keyword in keywords
    }


def _presence_score(content: str, keywords: list[str]) -> int:
    """Score keyword presence.

    Args:
        content: Content to analyze.
        keywords: Target keywords.

    Returns:
        Presence score between 0 and 30.
    """

    if not keywords:
        return 0
    lower_content = content.lower()
    present = sum(1 for keyword in keywords if keyword in lower_content)
    return round(present / len(keywords) * 30)


def _density_score(density: dict[str, float]) -> int:
    """Score keyword density against a 1-2 percent target.

    Args:
        density: Keyword density percentages.

    Returns:
        Density score between 0 and 30.
    """

    if not density:
        return 0
    scores = [30 if 1 <= value <= 2 else 20 if 0 < value < 3 else 10 if value > 0 else 0 for value in density.values()]
    return round(sum(scores) / len(scores))


def _has_heading_structure(content: str) -> bool:
    """Detect Markdown-style headings or title-case section starts.

    Args:
        content: Content to inspect.

    Returns:
        True when heading structure appears present.
    """

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return any(line.startswith("#") for line in lines) or sum(1 for line in lines if line.istitle()) >= 2


def _flesch_reading_ease(content: str) -> float:
    """Calculate a Flesch reading ease approximation.

    Args:
        content: Content to analyze.

    Returns:
        Flesch reading ease score.
    """

    sentences = max(1, len(re.findall(r"[.!?]+", content)))
    words = WORD_PATTERN.findall(content)
    word_count = max(1, len(words))
    syllables = sum(_count_syllables(word) for word in words)
    return 206.835 - 1.015 * (word_count / sentences) - 84.6 * (syllables / word_count)


def _count_syllables(word: str) -> int:
    """Approximate syllable count for readability scoring.

    Args:
        word: Word to count.

    Returns:
        Estimated syllable count.
    """

    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 1
    groups = re.findall(r"[aeiouy]+", cleaned)
    count = len(groups)
    if cleaned.endswith("e") and count > 1:
        count -= 1
    return max(1, count)

