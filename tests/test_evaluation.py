"""
Tests for the evaluation module (src/evaluation.py).

A tiny 4-song catalog is used with k large enough that every song is returned,
so the per-list metrics are exact and independent of ranking order. Two checks
use the real data/songs.csv catalog for the confidence/fallback aggregates.
"""

import pytest

from src.evaluation import evaluate_profile, evaluate_profiles
from src.recommender import load_songs


def song(**overrides) -> dict:
    base = {
        "id": 1, "title": "Track", "artist": "Artist",
        "genre": "pop", "mood": "happy",
        "energy": 0.8, "tempo_bpm": 120.0, "valence": 0.7,
        "danceability": 0.8, "acousticness": 0.2,
    }
    base.update(overrides)
    return base


# A controlled catalog: with k=10 all four songs are always returned.
CATALOG = [
    song(id=1, genre="pop", mood="happy", energy=0.8, acousticness=0.10),
    song(id=2, genre="pop", mood="sad", energy=0.6, acousticness=0.20),
    song(id=3, genre="rock", mood="happy", energy=0.9, acousticness=0.05),
    song(id=4, genre="lofi", mood="chill", energy=0.3, acousticness=0.90),
]
PREFS = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}


@pytest.fixture
def ev():
    return evaluate_profile("test", PREFS, CATALOG, k=10)


# --- One test per metric ---------------------------------------------------

def test_genre_match_rate(ev):
    # 2 of 4 songs are pop.
    assert ev.genre_match_rate == 0.5

def test_mood_match_rate(ev):
    # 2 of 4 songs are happy.
    assert ev.mood_match_rate == 0.5

def test_average_energy_error(ev):
    # |0.8-0.8|+|0.6-0.8|+|0.9-0.8|+|0.3-0.8| = 0.8; /4 = 0.2
    assert ev.average_energy_error == 0.2

def test_acoustic_match_rate(ev):
    # likes_acoustic False -> match if acousticness <= 0.5: 3 of 4 qualify.
    assert ev.acoustic_match_rate == 0.75

def test_attributes_satisfied_pct(ev):
    # Per song: 4/4, 2/4, 3/4, 0/4 -> mean = 0.5625
    assert ev.attributes_satisfied_pct == 0.5625

def test_n_recommendations(ev):
    assert ev.n_recommendations == 4


# --- Empty recommendation list is handled safely --------------------------

def test_empty_recommendations_are_safe():
    ev = evaluate_profile("empty", PREFS, [], k=5)
    assert ev.n_recommendations == 0
    assert ev.genre_match_rate == 0.0
    assert ev.mood_match_rate == 0.0
    assert ev.average_energy_error == 0.0
    assert ev.acoustic_match_rate == 0.0
    assert ev.attributes_satisfied_pct == 0.0


# --- Aggregate + confidence/fallback metrics on the real catalog ----------

def test_low_confidence_and_fallback_flags_real_catalog():
    songs = load_songs("data/songs.csv")
    adv = evaluate_profile(
        "adv", {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}, songs)
    edm = evaluate_profile(
        "edm", {"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False}, songs)
    assert adv.is_low_confidence is True and adv.fallback_triggered is True
    assert edm.is_low_confidence is False and edm.fallback_triggered is False


def test_evaluate_profiles_aggregate_counts():
    songs = load_songs("data/songs.csv")
    profiles = [
        ("adv", {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}),
        ("edm", {"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False}),
    ]
    summary = evaluate_profiles(profiles, songs, k=5)
    assert summary.n_profiles == 2
    assert summary.low_confidence_cases == 1
    assert summary.fallback_activation_rate == 0.5
    # Aggregate rates are within valid bounds.
    assert 0.0 <= summary.mean_genre_match_rate <= 1.0


def test_summary_text_is_readable():
    songs = load_songs("data/songs.csv")
    summary = evaluate_profiles([("edm", {"genre": "edm", "mood": "energetic",
                                          "target_energy": 0.95, "likes_acoustic": False})], songs)
    text = summary.summary_text()
    assert "Genre match rate" in text
    assert "Fallback activation rate" in text
