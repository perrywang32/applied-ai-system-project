"""
Fallback behavior for the Music Recommender.

When confidence is low, the top recommendation is not a strong, complete match.
Rather than present a weak match as if it were perfect, we switch to a
"fallback" presentation that:

  - clearly states that no strong complete match was found,
  - offers the closest available alternatives (the top of the normal ranking),
  - explains, per alternative, which preferences matched and which did not.

This module NEVER changes the ranking and never removes results. The normal
ranked output is still shown by main.py; this only adds an honest framing on
top of it. If alternatives exist, they are always returned (no empty result).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from src.confidence import MEDIUM_THRESHOLD, preference_breakdown

# Fallback kicks in when confidence falls into the "Low" band (below Medium).
FALLBACK_THRESHOLD = MEDIUM_THRESHOLD


@dataclass
class Alternative:
    """One close alternative plus which preferences it did / didn't meet."""
    title: str
    artist: str
    score: float
    matched: List[str]
    unmatched: List[str]


@dataclass
class FallbackResult:
    triggered: bool                 # True when confidence is below the threshold
    threshold: float
    confidence: float
    message: str                    # empty when not triggered
    alternatives: List[Alternative] = field(default_factory=list)


def build_fallback(
    prefs: Dict,
    ranked: List[Tuple[Dict, float, List[str]]],
    confidence,
    top_n: int = 3,
) -> FallbackResult:
    """
    Decide whether to fall back and, if so, describe the closest alternatives.

    `ranked` is the recommend_songs() output; `confidence` is a ConfidenceReport.
    """
    triggered = confidence.value < FALLBACK_THRESHOLD

    alternatives: List[Alternative] = []
    for song, score, _reasons in ranked[:top_n]:
        matched, unmatched = preference_breakdown(prefs, song)
        alternatives.append(Alternative(
            title=song.get("title", "(unknown)"),
            artist=song.get("artist", "(unknown)"),
            score=score,
            matched=matched,
            unmatched=unmatched,
        ))

    if not triggered:
        message = ""
    elif alternatives:
        message = (
            "No strong complete match was found for your preferences. "
            "Showing the closest available alternatives instead."
        )
    else:
        message = (
            "No strong complete match was found, and there are no alternatives "
            "available in the catalog."
        )

    return FallbackResult(
        triggered=triggered,
        threshold=FALLBACK_THRESHOLD,
        confidence=confidence.value,
        message=message,
        alternatives=alternatives,
    )
