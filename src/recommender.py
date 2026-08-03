import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from src.validation import (
    DatasetValidationError,
    NUMERIC_SONG_FIELDS,
    validate_columns,
)

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        # TODO: Implement explanation logic
        return "Explanation placeholder"

def load_songs(csv_path: str) -> List[Dict]:
    """Read the songs CSV and return a list of dicts, with number columns as floats.

    Validates the header columns and the numeric values as it parses. A missing
    column or a malformed/missing number raises a friendly DatasetValidationError
    (with the offending row and column) instead of a raw ValueError.
    """
    # Columns that hold measurements and should be parsed as floats.
    # Everything else (title, artist, genre, mood) stays a string.
    float_fields = NUMERIC_SONG_FIELDS

    songs: List[Dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)  # uses the header row for dict keys
        validate_columns(reader.fieldnames)  # fail early if a column is missing
        # Row 1 is the header, so data rows start at line 2.
        for line_no, row in enumerate(reader, start=2):
            song: Dict = {}
            for key, value in row.items():
                if key == "id":
                    song[key] = _parse_number(value, key, line_no, as_int=True)
                elif key in float_fields:
                    song[key] = _parse_number(value, key, line_no, as_int=False)
                else:
                    song[key] = value               # categorical -> keep as string
            songs.append(song)

    print(f"Loaded {len(songs)} songs from {csv_path}")
    return songs


def _parse_number(value, column: str, line_no: int, as_int: bool):
    """Parse a CSV cell as a number, raising a friendly DatasetValidationError on failure."""
    try:
        return int(value) if as_int else float(value)
    except (TypeError, ValueError):
        raise DatasetValidationError(
            f"Row {line_no}, column '{column}' has a malformed or missing number: {value!r}."
        )

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against the user's preferences and return (score, reasons)."""
    score = 0.0
    reasons: List[str] = []

    # --- Genre match: +3.0 (case-insensitive so "EDM" matches "edm") ---
    pref_genre = user_prefs.get("genre") or user_prefs.get("favorite_genre")
    if pref_genre and song["genre"].lower() == str(pref_genre).lower():
        score += 3.0
        reasons.append(f"Genre '{song['genre']}' matches your favorite (+3.0)")
    elif pref_genre:
        reasons.append(f"Genre '{song['genre']}' is not your favorite '{pref_genre}' (+0.0)")

    # --- Mood match: +2.0 ---
    pref_mood = user_prefs.get("mood") or user_prefs.get("favorite_mood")
    if pref_mood and song["mood"].lower() == str(pref_mood).lower():
        score += 2.0
        reasons.append(f"Mood '{song['mood']}' matches your favorite (+2.0)")
    elif pref_mood:
        reasons.append(f"Mood '{song['mood']}' is not your favorite '{pref_mood}' (+0.0)")

    # --- Energy closeness: 2 * (1 - |song energy - target|), up to +2.0 ---
    # Rewards CLOSENESS to the target, not simply higher energy.
    target_energy = user_prefs.get("target_energy", user_prefs.get("energy"))
    if target_energy is not None:
        energy_points = 2 * (1 - abs(song["energy"] - target_energy))
        score += energy_points
        reasons.append(
            f"Energy {song['energy']:.2f} vs target {target_energy:.2f} "
            f"({energy_points:+.2f})"
        )

    # --- Acousticness preference: up to +1.0 ---
    # likes_acoustic True  -> reward acoustic songs (points = acousticness)
    # likes_acoustic False -> reward non-acoustic songs (points = 1 - acousticness)
    likes_acoustic = user_prefs.get("likes_acoustic")
    if likes_acoustic is not None:
        if likes_acoustic:
            acoustic_points = 1.0 * song["acousticness"]
            label = "you like acoustic"
        else:
            acoustic_points = 1.0 * (1 - song["acousticness"])
            label = "you prefer non-acoustic"
        score += acoustic_points
        reasons.append(
            f"Acousticness {song['acousticness']:.2f} ({label}) ({acoustic_points:+.2f})"
        )

    return score, reasons

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, List[str]]]:
    """Score every song, rank them highest-first, and return the top k as (song, score, reasons)."""
    # Score every song. `*score_song(...)` unpacks its (score, reasons) tuple,
    # so each item becomes (song, score, reasons).
    scored = [(song, *score_song(user_prefs, song)) for song in songs]

    # Sort by score (item[1]) from highest to lowest. sorted() returns a NEW list
    # and leaves the caller's `songs` list untouched.
    ranked = sorted(scored, key=lambda item: item[1], reverse=True)

    # Return only the top k recommendations.
    return ranked[:k]
