"""
Automated tests for data-driven profile conflict detection (src/conflicts.py).

Each test builds a small, explicit catalog so the expected conflict is obvious,
plus two checks against the real data/songs.csv catalog.
"""

from src.conflicts import detect_conflicts
from src.recommender import load_songs


def song(**overrides) -> dict:
    base = {
        "id": 1,
        "title": "Track",
        "artist": "Artist",
        "genre": "pop",
        "mood": "happy",
        "energy": 0.8,
        "tempo_bpm": 120.0,
        "valence": 0.7,
        "danceability": 0.8,
        "acousticness": 0.2,
    }
    base.update(overrides)
    return base


def codes(prefs, songs) -> set:
    return {c.code for c in detect_conflicts(prefs, songs)}


# --- Happy path: no conflicts ---------------------------------------------

def test_coherent_profile_has_no_conflicts():
    catalog = [song(id=1, genre="pop", mood="happy", energy=0.8, acousticness=0.2)]
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    assert detect_conflicts(prefs, catalog) == []


# --- 1. genre not in catalog ----------------------------------------------

def test_genre_not_in_catalog():
    catalog = [song(genre="pop")]
    prefs = {"genre": "jazz", "mood": "happy", "energy": 0.8}
    assert "genre_not_in_catalog" in codes(prefs, catalog)


# --- 2. genre far from target energy --------------------------------------

def test_genre_energy_mismatch():
    # Only lofi songs exist, all low energy; user wants very high energy lofi.
    catalog = [song(id=1, genre="lofi", mood="chill", energy=0.35, acousticness=0.8)]
    prefs = {"genre": "lofi", "mood": "chill", "target_energy": 0.95}
    assert "genre_energy_mismatch" in codes(prefs, catalog)


# --- 3. genre + mood combination absent -----------------------------------

def test_genre_mood_absent():
    catalog = [song(genre="pop", mood="happy", energy=0.8)]
    prefs = {"genre": "pop", "mood": "sad", "energy": 0.8}
    result = codes(prefs, catalog)
    assert "genre_mood_absent" in result


# --- 4. acoustic preference unavailable in that genre ---------------------

def test_acoustic_unavailable():
    # Every pop song is non-acoustic, but the user wants acoustic.
    catalog = [song(genre="pop", mood="happy", energy=0.8, acousticness=0.1)]
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": True}
    assert "acoustic_unavailable" in codes(prefs, catalog)


# --- 5. no single song satisfies every property ---------------------------

def test_no_single_song_satisfies_all():
    # A song matches genre+mood, another matches energy+acoustic, but none matches all.
    catalog = [
        song(id=1, genre="pop", mood="happy", energy=0.2, acousticness=0.1),
        song(id=2, genre="rock", mood="intense", energy=0.9, acousticness=0.9),
    ]
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.9, "likes_acoustic": True}
    assert "no_single_song_satisfies_all" in codes(prefs, catalog)


# --- Against the real catalog ---------------------------------------------

def test_real_catalog_adversarial_profile_flags_conflicts():
    songs = load_songs("data/songs.csv")
    prefs = {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}
    result = codes(prefs, songs)
    # Metal's one song is loud, angry, and non-acoustic -> several conflicts expected.
    assert "genre_energy_mismatch" in result
    assert "genre_mood_absent" in result
    assert "acoustic_unavailable" in result
    assert "no_single_song_satisfies_all" in result


def test_real_catalog_coherent_edm_profile_has_no_conflicts():
    songs = load_songs("data/songs.csv")
    prefs = {"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False}
    assert detect_conflicts(prefs, songs) == []
