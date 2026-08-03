"""
Tests for fallback behavior (src/fallback.py) plus a main() integration check.

Covers: the normal (high-confidence) case where fallback does NOT trigger, the
low-confidence case where it does, the matched/unmatched breakdown, and that
alternatives are preserved (never empty) when songs exist.
"""

from src.confidence import score_confidence
from src.conflicts import detect_conflicts
from src.fallback import build_fallback, FALLBACK_THRESHOLD
from src.recommender import load_songs, recommend_songs


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
    return [(s, score, []) for s, score in pairs]


# --- Normal case: strong match, no fallback -------------------------------

def test_no_fallback_on_high_confidence():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    top = song(genre="pop", mood="happy", energy=0.8, acousticness=0.1)
    ranked = ranked_from([(top, 8.0), (song(id=2), 2.0)])
    confidence = score_confidence(prefs, ranked)

    fb = build_fallback(prefs, ranked, confidence)
    assert fb.triggered is False
    assert fb.message == ""


# --- Fallback case: weak match ---------------------------------------------

def test_fallback_triggers_on_low_confidence():
    # Adversarial metal/chill/low-energy/acoustic profile.
    top = song(genre="ambient", mood="chill", energy=0.28, acousticness=0.92, title="Spacewalk")
    second = song(id=2, genre="lofi", mood="chill", energy=0.35, acousticness=0.86, title="Library Rain")
    prefs = {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}
    ranked = ranked_from([(top, 4.56), (second, 4.36)])
    confidence = score_confidence(prefs, ranked, conflicts=[object()])

    fb = build_fallback(prefs, ranked, confidence)
    assert fb.triggered is True
    assert fb.confidence < FALLBACK_THRESHOLD
    assert "no strong complete match" in fb.message.lower()


def test_fallback_alternatives_are_not_empty_when_songs_exist():
    top = song(genre="ambient", mood="chill", energy=0.28, acousticness=0.92)
    prefs = {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}
    ranked = ranked_from([(top, 4.56), (song(id=2), 4.36), (song(id=3), 4.0)])
    confidence = score_confidence(prefs, ranked, conflicts=[object()])

    fb = build_fallback(prefs, ranked, confidence)
    assert len(fb.alternatives) >= 1


def test_fallback_explains_matched_and_unmatched():
    # Top matches mood + acoustic, but misses genre + energy.
    top = song(genre="ambient", mood="chill", energy=0.28, acousticness=0.92)
    prefs = {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}
    ranked = ranked_from([(top, 4.56), (song(id=2), 4.36)])
    confidence = score_confidence(prefs, ranked, conflicts=[object()])

    fb = build_fallback(prefs, ranked, confidence)
    alt = fb.alternatives[0]
    assert "Mood matched" in alt.matched
    assert "Acoustic preference matched" in alt.matched
    assert "Genre did not match" in alt.unmatched


# --- Against the real catalog ---------------------------------------------

def test_real_catalog_coherent_profile_no_fallback():
    songs = load_songs("data/songs.csv")
    prefs = {"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False}
    ranked = recommend_songs(prefs, songs, k=5)
    confidence = score_confidence(prefs, ranked, detect_conflicts(prefs, songs))
    assert build_fallback(prefs, ranked, confidence).triggered is False


def test_real_catalog_adversarial_profile_falls_back():
    songs = load_songs("data/songs.csv")
    prefs = {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}
    ranked = recommend_songs(prefs, songs, k=5)
    confidence = score_confidence(prefs, ranked, detect_conflicts(prefs, songs))
    fb = build_fallback(prefs, ranked, confidence)
    assert fb.triggered is True
    assert len(fb.alternatives) >= 1


# --- Integration: main() runs both paths without crashing ------------------

def test_main_runs_and_shows_confidence(capsys):
    from src import main as main_module
    main_module.main()
    out = capsys.readouterr().out
    # Default profile is a strong match: recommendations + confidence shown,
    # and NO fallback banner.
    assert "TOP MUSIC RECOMMENDATIONS" in out
    assert "Confidence:" in out
    assert "NO STRONG MATCH FOUND" not in out
