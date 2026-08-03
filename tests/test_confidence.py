"""
Tests for the explainable confidence system (src/confidence.py).

Covers: label boundaries, the 0..1 bound, weak/partial matches, exact-match
detection, the conflict penalty, single-candidate separation, and determinism.
"""

import pytest

from src.confidence import (
    MAX_SCORE,
    confidence_label,
    score_confidence,
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
)


def song(**overrides) -> dict:
    base = {
        "id": 1, "title": "Track", "artist": "Artist",
        "genre": "pop", "mood": "happy",
        "energy": 0.8, "tempo_bpm": 120.0, "valence": 0.7,
        "danceability": 0.8, "acousticness": 0.2,
    }
    base.update(overrides)
    return base


def ranked_from(pairs) -> list:
    """Build a recommend_songs-style list: [(song, score, reasons), ...]."""
    return [(s, score, []) for s, score in pairs]


POP_PREFS = {"genre": "pop", "mood": "happy", "energy": 0.8}


# --- Label boundaries ------------------------------------------------------

@pytest.mark.parametrize("value,label", [
    (0.0, "Low"),
    (MEDIUM_THRESHOLD - 0.01, "Low"),
    (MEDIUM_THRESHOLD, "Medium"),
    (HIGH_THRESHOLD - 0.01, "Medium"),
    (HIGH_THRESHOLD, "High"),
    (1.0, "High"),
])
def test_confidence_label_boundaries(value, label):
    assert confidence_label(value) == label


# --- Value stays within 0..1 ----------------------------------------------

@pytest.mark.parametrize("s1,s2", [(0.0, 0.0), (8.0, 0.0), (3.0, 2.9), (8.0, 7.9), (5.0, 1.0)])
def test_value_always_within_bounds(s1, s2):
    report = score_confidence(POP_PREFS, ranked_from([(song(), s1), (song(id=2), s2)]))
    assert 0.0 <= report.value <= 1.0


def test_empty_ranked_is_zero_and_low():
    report = score_confidence(POP_PREFS, [])
    assert report.value == 0.0
    assert report.label == "Low"
    assert report.is_exact_match is False


# --- Strong match -> High --------------------------------------------------

def test_perfect_match_is_high():
    top = song(genre="pop", mood="happy", energy=0.8, acousticness=0.1)
    report = score_confidence(POP_PREFS, ranked_from([(top, MAX_SCORE), (song(id=2), 2.0)]))
    assert report.label == "High"
    assert report.is_exact_match is True
    assert report.satisfied == report.requested == 3


# --- Weak / partial match -> Low ------------------------------------------

def test_weak_conflicting_match_is_low():
    # Top song matches only mood + acoustic (adversarial metal/chill profile).
    top = song(genre="ambient", mood="chill", energy=0.28, acousticness=0.92, title="Spacewalk")
    second = song(id=2, genre="lofi", mood="chill", energy=0.35, acousticness=0.86, title="Library Rain")
    prefs = {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}
    report = score_confidence(prefs, ranked_from([(top, 4.56), (second, 4.36)]), conflicts=[object()])
    assert report.label == "Low"
    assert report.is_exact_match is False


# --- Conflict penalty lowers confidence -----------------------------------

def test_conflict_penalty_lowers_confidence():
    top = song(genre="pop", mood="happy", energy=0.8, acousticness=0.1)
    ranked = ranked_from([(top, 6.96), (song(id=2), 4.0)])
    without = score_confidence(POP_PREFS, ranked, conflicts=[])
    with_conflict = score_confidence(POP_PREFS, ranked, conflicts=[object()])
    assert with_conflict.value < without.value


# --- Single candidate: separation is full ---------------------------------

def test_single_candidate_separation_is_full():
    top = song(genre="pop", mood="happy", energy=0.8)
    report = score_confidence(POP_PREFS, ranked_from([(top, 6.96)]))
    assert report.components["separation"] == 1.0


# --- Per-preference reasons (the presentation format) ---------------------

def test_reasons_are_per_preference():
    # Genre + mood match, energy off by 0.12 (still within tolerance),
    # user wants acoustic but the song is not acoustic.
    top = song(genre="pop", mood="happy", energy=0.68, acousticness=0.10)
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": True}
    report = score_confidence(prefs, ranked_from([(top, 7.0), (song(id=2), 3.0)]))

    assert report.reasons == [
        "Genre matched",
        "Mood matched",
        "Energy difference was 0.12",
        "Acoustic preference did not match",
    ]
    # 3 of 4 satisfied, not an exact match -> a Medium-ish, sub-1.0 result.
    assert report.satisfied == 3 and report.requested == 4
    assert report.is_exact_match is False
    assert report.label == "Medium"


# --- Determinism -----------------------------------------------------------

def test_confidence_is_deterministic():
    ranked = ranked_from([(song(), 6.0), (song(id=2), 3.0)])
    a = score_confidence(POP_PREFS, ranked)
    b = score_confidence(POP_PREFS, ranked)
    assert a.value == b.value
    assert a.label == b.label
    assert a.components == b.components
