"""
Explainable recommendation confidence for the Music Recommender.

WHY NOT JUST USE THE RAW SCORE?
    The raw score (0..8) says how well the *top song* matched, but not how much
    to TRUST the result. A song can score highly while (a) barely beating the
    runner-up, (b) satisfying only some of the user's stated preferences, or
    (c) coming from a profile we already flagged as conflicting. Confidence
    combines several independent pieces of evidence into one 0..1 number.

THE FORMULA (simple, deterministic, and easy to explain):

    confidence = base * penalties

    base = 0.50 * match_quality      # how good the top match is
         + 0.20 * separation         # how clearly #1 beats #2
         + 0.30 * coverage           # how many stated prefs the top song meets

    where each part is already scaled to 0..1:
        match_quality = top_score / 8.0            (8.0 = max possible score)
        separation    = min(1, (score1 - score2) / 2.0)   (a 2-pt lead = full)
        coverage      = (preferences satisfied) / (preferences requested)

    penalties (each keeps the value in 0..1 because they are <= 1):
        * 0.85  if the top song is a FALLBACK match (not all prefs satisfied)
        * 0.75  if a profile CONFLICT was detected

    label:  >= 0.80 High   |   >= 0.50 Medium   |   else Low
            (High requires a near-perfect match; one missed preference -> Medium)

Every input is fixed data, so the same profile + catalog always yields the same
confidence (deterministic).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

# Reuse the SAME thresholds the conflict detector uses, so "satisfied" means the
# same thing everywhere in the project.
from src.conflicts import ACOUSTIC_CUTOFF, ENERGY_NEAR


# --- Constants (the whole formula lives here, named for explainability) ----

MAX_SCORE = 8.0            # genre 3 + mood 2 + energy 2 + acoustic 1 (see score_song)
SEPARATION_REF = 2.0       # a 2-point lead over #2 counts as a "clear" win

W_QUALITY = 0.50           # weights sum to 1.0
W_SEPARATION = 0.20
W_COVERAGE = 0.30

FALLBACK_PENALTY = 0.85    # applied when the top song isn't an exact match
CONFLICT_PENALTY = 0.75    # applied when a profile conflict was detected

# High requires a near-perfect result; a single missed preference (e.g. a
# fallback match) should land in Medium, and a conflicted/weak match in Low.
HIGH_THRESHOLD = 0.80
MEDIUM_THRESHOLD = 0.50


@dataclass
class ConfidenceReport:
    """The confidence result plus the evidence behind it (for display/tests)."""
    value: float                     # final confidence, 0..1
    label: str                       # "High" / "Medium" / "Low"
    components: Dict[str, float]     # match_quality, separation, coverage
    satisfied: int                   # stated prefs the top song meets
    requested: int                   # stated prefs in the profile
    is_exact_match: bool             # top song meets ALL stated prefs
    conflict_detected: bool
    reasons: List[str] = field(default_factory=list)  # per-preference, plain English
    factors: List[str] = field(default_factory=list)  # the weighted-math breakdown


# --- Small helpers ---------------------------------------------------------

def _clamp(x: float) -> float:
    """Keep a value inside 0..1."""
    return max(0.0, min(1.0, x))


def _same(a: Any, b: Any) -> bool:
    return str(a).strip().lower() == str(b).strip().lower()


def _get_genre(prefs: Dict): return prefs.get("genre") or prefs.get("favorite_genre")
def _get_mood(prefs: Dict): return prefs.get("mood") or prefs.get("favorite_mood")
def _get_energy(prefs: Dict):
    energy = prefs.get("target_energy")
    return energy if energy is not None else prefs.get("energy")


def _explain_top(prefs: Dict, song: Dict) -> Tuple[int, int, List[str]]:
    """
    Check each stated preference against the top song.

    Returns (satisfied_count, requested_count, reasons) where `reasons` is a
    plain-English line per preference, e.g. "Genre matched" or
    "Energy difference was 0.12".
    """
    genre, mood = _get_genre(prefs), _get_mood(prefs)
    energy, likes_acoustic = _get_energy(prefs), prefs.get("likes_acoustic")

    satisfied = 0
    requested = 0
    reasons: List[str] = []

    if genre:
        requested += 1
        ok = _same(song.get("genre", ""), genre)
        satisfied += int(ok)
        reasons.append("Genre matched" if ok else "Genre did not match")

    if mood:
        requested += 1
        ok = _same(song.get("mood", ""), mood)
        satisfied += int(ok)
        reasons.append("Mood matched" if ok else "Mood did not match")

    if energy is not None:
        requested += 1
        difference = abs(song["energy"] - energy)
        satisfied += int(difference <= ENERGY_NEAR)
        reasons.append(f"Energy difference was {difference:.2f}")

    if isinstance(likes_acoustic, bool):
        requested += 1
        if likes_acoustic:
            ok = song["acousticness"] >= ACOUSTIC_CUTOFF
        else:
            ok = song["acousticness"] <= ACOUSTIC_CUTOFF
        satisfied += int(ok)
        reasons.append("Acoustic preference matched" if ok else "Acoustic preference did not match")

    return satisfied, requested, reasons


# --- Public API ------------------------------------------------------------

def confidence_label(value: float) -> str:
    """Map a 0..1 confidence value to a High / Medium / Low label."""
    if value >= HIGH_THRESHOLD:
        return "High"
    if value >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def score_confidence(
    prefs: Dict,
    ranked: List[Tuple[Dict, float, List[str]]],
    conflicts: Optional[list] = None,
) -> ConfidenceReport:
    """
    Compute an explainable confidence for a ranked recommendation list.

    `ranked` is the output of recommend_songs(): a list of (song, score, reasons).
    `conflicts` is the (optional) list from detect_conflicts().
    """
    conflict_detected = bool(conflicts)

    # No results -> zero confidence.
    if not ranked:
        return ConfidenceReport(
            value=0.0, label="Low",
            components={"match_quality": 0.0, "separation": 0.0, "coverage": 0.0},
            satisfied=0, requested=0, is_exact_match=False,
            conflict_detected=conflict_detected,
            reasons=["No recommendations available"],
            factors=["No recommendations available -> confidence 0.00 (Low)."],
        )

    top_song, top_score, _ = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else None

    # --- Evidence, each scaled to 0..1 ---
    match_quality = _clamp(top_score / MAX_SCORE)

    if second_score is None:
        separation = 1.0  # only one candidate -> nothing competes with it
    else:
        separation = _clamp((top_score - second_score) / SEPARATION_REF)

    satisfied, requested, reasons = _explain_top(prefs, top_song)
    coverage = satisfied / requested if requested else 1.0
    is_exact_match = satisfied == requested

    # --- Combine, then apply penalties (all multipliers <= 1 keep us in 0..1) ---
    value = (W_QUALITY * match_quality
             + W_SEPARATION * separation
             + W_COVERAGE * coverage)
    if not is_exact_match:
        value *= FALLBACK_PENALTY
    if conflict_detected:
        value *= CONFLICT_PENALTY

    value = round(_clamp(value), 2)
    label = confidence_label(value)

    components = {
        "match_quality": round(match_quality, 2),
        "separation": round(separation, 2),
        "coverage": round(coverage, 2),
    }

    if second_score is None:
        separation_line = f"Only one candidate -> separation {separation:.2f} (weight {W_SEPARATION})"
    else:
        separation_line = (
            f"Lead over #2: {top_score - second_score:.2f} pts -> {separation:.2f} "
            f"(weight {W_SEPARATION})"
        )

    factors = [
        f"Top match quality: {top_score:.2f}/{MAX_SCORE:.0f} = {match_quality:.2f} (weight {W_QUALITY})",
        separation_line,
        f"Preferences satisfied: {satisfied}/{requested} = {coverage:.2f} (weight {W_COVERAGE})",
        f"Exact match: {'yes' if is_exact_match else f'no (fallback x{FALLBACK_PENALTY})'}",
        f"Conflict detected: {'yes (x' + str(CONFLICT_PENALTY) + ')' if conflict_detected else 'no'}",
        f"=> Confidence {value:.2f} ({label})",
    ]

    return ConfidenceReport(
        value=value, label=label, components=components,
        satisfied=satisfied, requested=requested,
        is_exact_match=is_exact_match, conflict_detected=conflict_detected,
        reasons=reasons, factors=factors,
    )
