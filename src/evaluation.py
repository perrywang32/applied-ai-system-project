"""
Evaluation metrics for the Music Recommender.

This module measures recommendation quality with simple, DETERMINISTIC metrics
computed from the *real* recommendation output. It runs the actual pipeline
(recommend_songs -> detect_conflicts -> score_confidence -> build_fallback) for
each profile, so it is connected to the live system rather than being a
standalone example.

Per-recommendation-list metrics (over the songs actually returned):
  - genre_match_rate         fraction whose genre matches the requested genre
  - mood_match_rate          fraction whose mood matches the requested mood
  - average_energy_error     mean |song energy - target energy|
  - acoustic_match_rate      fraction matching the acoustic preference
  - attributes_satisfied_pct mean fraction of stated preferences met per song

Per-profile / aggregate metrics:
  - is_low_confidence / low_confidence_cases
  - fallback_triggered / fallback_activation_rate

Empty recommendation lists are handled safely (no division by zero): rates and
errors default to 0.0.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.confidence import preference_breakdown, score_confidence
from src.conflicts import ACOUSTIC_CUTOFF, detect_conflicts
from src.fallback import build_fallback
from src.recommender import recommend_songs


# --- Preference extraction (same spellings the rest of the app accepts) ----

def _get_genre(prefs: Dict): return prefs.get("genre") or prefs.get("favorite_genre")
def _get_mood(prefs: Dict): return prefs.get("mood") or prefs.get("favorite_mood")
def _get_energy(prefs: Dict):
    energy = prefs.get("target_energy")
    return energy if energy is not None else prefs.get("energy")


def _same(a, b) -> bool:
    return str(a).strip().lower() == str(b).strip().lower()


def _mean(values) -> Optional[float]:
    """Mean of the non-None values, rounded; None if there are none."""
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


@dataclass
class ProfileEvaluation:
    """Metrics for a single profile's recommendations."""
    label: str
    n_recommendations: int
    genre_match_rate: Optional[float]
    mood_match_rate: Optional[float]
    average_energy_error: Optional[float]
    acoustic_match_rate: Optional[float]
    attributes_satisfied_pct: float
    confidence: float
    confidence_label: str
    is_low_confidence: bool
    fallback_triggered: bool


@dataclass
class EvaluationSummary:
    """Aggregate metrics across several profiles."""
    n_profiles: int
    per_profile: List[ProfileEvaluation] = field(default_factory=list)
    mean_genre_match_rate: Optional[float] = None
    mean_mood_match_rate: Optional[float] = None
    mean_energy_error: Optional[float] = None
    mean_acoustic_match_rate: Optional[float] = None
    mean_attributes_satisfied_pct: Optional[float] = None
    low_confidence_cases: int = 0
    fallback_activation_rate: float = 0.0

    def summary_text(self) -> str:
        """A short, README-friendly text summary of the aggregate metrics."""
        def pct(x): return "n/a" if x is None else f"{x:.2f}"
        lines = [
            f"Evaluated {self.n_profiles} profiles against the catalog:",
            f"  Genre match rate:            {pct(self.mean_genre_match_rate)}",
            f"  Mood match rate:             {pct(self.mean_mood_match_rate)}",
            f"  Average energy error:        {pct(self.mean_energy_error)}",
            f"  Acoustic match rate:         {pct(self.mean_acoustic_match_rate)}",
            f"  Attributes satisfied:        {pct(self.mean_attributes_satisfied_pct)}",
            f"  Low-confidence cases:        {self.low_confidence_cases}/{self.n_profiles}",
            f"  Fallback activation rate:    {self.fallback_activation_rate:.2f}",
        ]
        return "\n".join(lines)


def evaluate_profile(label: str, prefs: Dict, songs: List[Dict], k: int = 5) -> ProfileEvaluation:
    """Run the real pipeline for one profile and compute its quality metrics."""
    recommendations = recommend_songs(prefs, songs, k=k)
    conflicts = detect_conflicts(prefs, songs)
    confidence = score_confidence(prefs, recommendations, conflicts)
    fallback = build_fallback(prefs, recommendations, confidence)

    rec_songs = [song for song, _score, _reasons in recommendations]
    n = len(rec_songs)

    genre, mood = _get_genre(prefs), _get_mood(prefs)
    energy, likes_acoustic = _get_energy(prefs), prefs.get("likes_acoustic")

    def rate(predicate) -> float:
        return round(sum(1 for s in rec_songs if predicate(s)) / n, 4) if n else 0.0

    genre_rate = rate(lambda s: _same(s["genre"], genre)) if genre else None
    mood_rate = rate(lambda s: _same(s["mood"], mood)) if mood else None

    if energy is None:
        energy_error = None
    elif n:
        energy_error = round(sum(abs(s["energy"] - energy) for s in rec_songs) / n, 4)
    else:
        energy_error = 0.0

    if isinstance(likes_acoustic, bool):
        if likes_acoustic:
            acoustic_rate = rate(lambda s: s["acousticness"] >= ACOUSTIC_CUTOFF)
        else:
            acoustic_rate = rate(lambda s: s["acousticness"] <= ACOUSTIC_CUTOFF)
    else:
        acoustic_rate = None

    # Percentage of requested attributes satisfied, averaged over the songs.
    if n:
        ratios = []
        for s in rec_songs:
            matched, unmatched = preference_breakdown(prefs, s)
            requested = len(matched) + len(unmatched)
            if requested:
                ratios.append(len(matched) / requested)
        attributes_satisfied_pct = round(sum(ratios) / len(ratios), 4) if ratios else 0.0
    else:
        attributes_satisfied_pct = 0.0

    return ProfileEvaluation(
        label=label,
        n_recommendations=n,
        genre_match_rate=genre_rate,
        mood_match_rate=mood_rate,
        average_energy_error=energy_error,
        acoustic_match_rate=acoustic_rate,
        attributes_satisfied_pct=attributes_satisfied_pct,
        confidence=confidence.value,
        confidence_label=confidence.label,
        is_low_confidence=(confidence.label == "Low"),
        fallback_triggered=fallback.triggered,
    )


def evaluate_profiles(
    profiles: List[Tuple[str, Dict]], songs: List[Dict], k: int = 5
) -> EvaluationSummary:
    """Evaluate several (label, prefs) profiles and aggregate the metrics."""
    per_profile = [evaluate_profile(label, prefs, songs, k=k) for label, prefs in profiles]
    n = len(per_profile)

    fallback_rate = (
        round(sum(1 for p in per_profile if p.fallback_triggered) / n, 4) if n else 0.0
    )

    return EvaluationSummary(
        n_profiles=n,
        per_profile=per_profile,
        mean_genre_match_rate=_mean(p.genre_match_rate for p in per_profile),
        mean_mood_match_rate=_mean(p.mood_match_rate for p in per_profile),
        mean_energy_error=_mean(p.average_energy_error for p in per_profile),
        mean_acoustic_match_rate=_mean(p.acoustic_match_rate for p in per_profile),
        mean_attributes_satisfied_pct=_mean(p.attributes_satisfied_pct for p in per_profile),
        low_confidence_cases=sum(1 for p in per_profile if p.is_low_confidence),
        fallback_activation_rate=fallback_rate,
    )
