"""
Input validation for the Music Recommender.

This module is the single place where we check that the data flowing into the
recommender is well-formed *before* any scoring happens. It reuses the project's
existing data shapes:

- user preferences: a plain dict (the same ``user_prefs`` used by ``score_song``)
- songs: a list of dicts (the same shape ``load_songs`` returns)

Nothing here changes how recommendations are calculated. It only rejects bad
input early with clear, user-friendly error messages.
"""

from typing import Dict, List, Optional, Tuple, Any


# --- Error types -----------------------------------------------------------
# One base class so callers (e.g. main.py) can catch every validation problem
# with a single `except ValidationError`. The subclasses let tests and callers
# distinguish *what kind* of input was bad.

class ValidationError(Exception):
    """Base class for all input-validation problems."""


class ProfileValidationError(ValidationError):
    """The user's preference profile is missing or malformed."""


class DatasetValidationError(ValidationError):
    """The song dataset is empty, malformed, or missing required fields."""


class ParameterValidationError(ValidationError):
    """A call parameter (such as top-k) is invalid."""


# --- Shared constants ------------------------------------------------------
# Kept here so both this module and load_songs() agree on the schema.

REQUIRED_SONG_COLUMNS: List[str] = [
    "id", "title", "artist", "genre", "mood",
    "energy", "tempo_bpm", "valence", "danceability", "acousticness",
]

# Fields that must parse as numbers.
NUMERIC_SONG_FIELDS = {"energy", "tempo_bpm", "valence", "danceability", "acousticness"}

# Numeric fields that must additionally fall inside the 0..1 range.
UNIT_INTERVAL_FIELDS = {"energy", "valence", "danceability", "acousticness"}

# Accepted range for the user's requested energy.
ENERGY_MIN = 0.0
ENERGY_MAX = 1.0


# --- Small helpers ---------------------------------------------------------

def _is_number(value: Any) -> bool:
    """True for real int/float values. Booleans are rejected (True is not energy)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _pick(prefs: Dict, *keys: str) -> Tuple[Optional[str], Any]:
    """Return (key, value) for the first key that is actually present, else (None, None)."""
    for key in keys:
        if key in prefs:
            return key, prefs[key]
    return None, None


# --- Profile validation ----------------------------------------------------

def validate_user_prefs(prefs: Dict) -> Dict:
    """
    Validate a user preference dict and return a normalized copy.

    Required: a genre, a mood, and a target energy (either key spelling is fine).
    Optional: likes_acoustic (must be a boolean if present).

    Raises ProfileValidationError with a friendly message on any problem.
    Normalization only trims surrounding whitespace on genre/mood and coerces
    energy to float; it never changes the meaning of the input.
    """
    if not isinstance(prefs, dict):
        raise ProfileValidationError("User preferences must be provided as a dictionary.")

    normalized = dict(prefs)

    # Genre -----------------------------------------------------------------
    genre_key, genre_val = _pick(prefs, "genre", "favorite_genre")
    if genre_key is None:
        raise ProfileValidationError(
            "Missing required preference: 'genre' (or 'favorite_genre')."
        )
    if not isinstance(genre_val, str) or not genre_val.strip():
        raise ProfileValidationError(
            "Preference 'genre' must be a non-empty text value (it was blank or not text)."
        )
    normalized[genre_key] = genre_val.strip()

    # Mood ------------------------------------------------------------------
    mood_key, mood_val = _pick(prefs, "mood", "favorite_mood")
    if mood_key is None:
        raise ProfileValidationError(
            "Missing required preference: 'mood' (or 'favorite_mood')."
        )
    if not isinstance(mood_val, str) or not mood_val.strip():
        raise ProfileValidationError(
            "Preference 'mood' must be a non-empty text value (it was blank or not text)."
        )
    normalized[mood_key] = mood_val.strip()

    # Energy ----------------------------------------------------------------
    energy_key, energy_val = _pick(prefs, "target_energy", "energy")
    if energy_key is None:
        raise ProfileValidationError(
            "Missing required preference: 'target_energy' (or 'energy')."
        )
    if not _is_number(energy_val):
        raise ProfileValidationError(
            f"Preference 'energy' must be a number between {ENERGY_MIN} and {ENERGY_MAX}; "
            f"got {energy_val!r}."
        )
    if not (ENERGY_MIN <= energy_val <= ENERGY_MAX):
        raise ProfileValidationError(
            f"Preference 'energy' must be between {ENERGY_MIN} and {ENERGY_MAX}; got {energy_val}."
        )
    normalized[energy_key] = float(energy_val)

    # Acoustic (optional) ---------------------------------------------------
    if "likes_acoustic" in prefs and not isinstance(prefs["likes_acoustic"], bool):
        raise ProfileValidationError(
            f"Preference 'likes_acoustic' must be true or false; got {prefs['likes_acoustic']!r}."
        )

    return normalized


# --- Parameter validation --------------------------------------------------

def validate_top_k(k: Any) -> int:
    """Validate the number of recommendations requested. Must be an integer >= 1."""
    if isinstance(k, bool) or not isinstance(k, int):
        raise ParameterValidationError(
            f"top-k (number of recommendations) must be a whole number; got {k!r}."
        )
    if k < 1:
        raise ParameterValidationError(
            f"top-k (number of recommendations) must be at least 1; got {k}."
        )
    return k


# --- Dataset validation ----------------------------------------------------

def validate_columns(fieldnames: Optional[List[str]]) -> None:
    """Check that a CSV header contains every required column. Used by load_songs()."""
    if not fieldnames:
        raise DatasetValidationError("Song dataset has no header row / columns.")
    missing = [col for col in REQUIRED_SONG_COLUMNS if col not in fieldnames]
    if missing:
        raise DatasetValidationError(
            f"Song dataset is missing required column(s): {', '.join(missing)}."
        )


def validate_dataset(songs: Any) -> List[Dict]:
    """
    Validate an already-loaded list of song dicts.

    Checks: the dataset is a non-empty list; every song has all required
    columns; numeric fields are real numbers; 0..1 fields are in range.
    Raises DatasetValidationError with a friendly message on any problem.
    """
    if not isinstance(songs, list):
        raise DatasetValidationError("Song dataset must be a list of songs.")
    if len(songs) == 0:
        raise DatasetValidationError("Song dataset is empty - there are no songs to recommend.")

    for index, song in enumerate(songs, start=1):
        if not isinstance(song, dict):
            raise DatasetValidationError(f"Song #{index} is not a valid record.")

        missing = [col for col in REQUIRED_SONG_COLUMNS if col not in song]
        if missing:
            raise DatasetValidationError(
                f"Song #{index} is missing required field(s): {', '.join(missing)}."
            )

        label = song.get("title", f"#{index}")
        for field in NUMERIC_SONG_FIELDS:
            value = song[field]
            if not _is_number(value):
                raise DatasetValidationError(
                    f"Song '{label}' has a malformed or missing {field} value: {value!r}."
                )
            if field in UNIT_INTERVAL_FIELDS and not (0.0 <= value <= 1.0):
                raise DatasetValidationError(
                    f"Song '{label}' has {field}={value}, which is outside the allowed 0.0 to 1.0 range."
                )

    return songs
