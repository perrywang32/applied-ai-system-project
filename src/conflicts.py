"""
Profile conflict detection for the Music Recommender.

Given a validated user profile and the *actual* song catalog, this module looks
for preference combinations that the available songs cannot satisfy well, and
returns clear warnings. It never rejects input — validation already did that.
The recommender still runs; these warnings just set honest expectations.

Everything here is DATA-DRIVEN: every check inspects the real songs in the
dataset. There are no hard-coded assumptions like "metal is loud" or "folk is
acoustic". If the catalog changes, the warnings change with it.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


# --- Tunable thresholds (named so the logic is explainable) ----------------

# A song counts as "acoustic" at or above this acousticness; "non-acoustic" below.
ACOUSTIC_CUTOFF = 0.5

# For the "no single song satisfies everything" check, a song's energy must be
# within this distance of the target to count as an energy match.
ENERGY_NEAR = 0.15

# For the per-genre energy check, we warn only when even the *closest* song in
# the requested genre is farther than this from the target energy.
ENERGY_FAR = 0.30


@dataclass
class Conflict:
    """One detected conflict: a stable `code` (for tests) and a friendly `message`."""
    code: str
    message: str


# --- Preference extraction (mirrors how score_song reads a profile) --------

def _get_genre(prefs: Dict) -> Optional[str]:
    return prefs.get("genre") or prefs.get("favorite_genre")


def _get_mood(prefs: Dict) -> Optional[str]:
    return prefs.get("mood") or prefs.get("favorite_mood")


def _get_energy(prefs: Dict) -> Optional[float]:
    energy = prefs.get("target_energy")
    if energy is None:
        energy = prefs.get("energy")
    return energy


def _same(a: Any, b: Any) -> bool:
    """Case-insensitive text equality (so 'EDM' matches 'edm')."""
    return str(a).strip().lower() == str(b).strip().lower()


def _satisfies_all(song: Dict, genre, mood, energy, likes_acoustic) -> bool:
    """True if this single song matches every preference the user actually stated."""
    if genre and not _same(song.get("genre", ""), genre):
        return False
    if mood and not _same(song.get("mood", ""), mood):
        return False
    if energy is not None and abs(song["energy"] - energy) > ENERGY_NEAR:
        return False
    if isinstance(likes_acoustic, bool):
        if likes_acoustic and song["acousticness"] < ACOUSTIC_CUTOFF:
            return False
        if not likes_acoustic and song["acousticness"] > ACOUSTIC_CUTOFF:
            return False
    return True


# --- Main entry point ------------------------------------------------------

def detect_conflicts(prefs: Dict, songs: List[Dict]) -> List[Conflict]:
    """
    Inspect the catalog and return warnings for hard-to-satisfy preferences.

    Checks (each grounded in the real songs):
      1. genre_not_in_catalog       - no song matches the requested genre
      2. genre_energy_mismatch      - the genre's songs are all far from target energy
      3. genre_mood_absent          - the genre exists, but not in the requested mood
      4. acoustic_unavailable       - the genre has no song matching the acoustic preference
      5. no_single_song_satisfies_all - nothing matches every stated preference at once
    """
    conflicts: List[Conflict] = []

    if not songs:
        return conflicts  # nothing to compare against; dataset validation handles emptiness

    genre = _get_genre(prefs)
    mood = _get_mood(prefs)
    energy = _get_energy(prefs)
    likes_acoustic = prefs.get("likes_acoustic")

    # Songs actually in the requested genre (case-insensitive).
    genre_songs = [s for s in songs if genre and _same(s.get("genre", ""), genre)]

    # 1. Requested genre missing from the catalog entirely.
    if genre and not genre_songs:
        conflicts.append(Conflict(
            "genre_not_in_catalog",
            f"No songs in the catalog match your genre '{genre}'.",
        ))

    # 2. The genre exists, but its songs are all far from the target energy.
    if genre_songs and energy is not None:
        closest = min(genre_songs, key=lambda s: abs(s["energy"] - energy))
        distance = abs(closest["energy"] - energy)
        if distance > ENERGY_FAR:
            conflicts.append(Conflict(
                "genre_energy_mismatch",
                f"Your genre '{genre}' has no song near your target energy {energy:.2f} "
                f"(the closest is {closest['energy']:.2f} in '{closest['title']}').",
            ))

    # 3. The genre exists, but not in the requested mood.
    if genre_songs and mood:
        if not any(_same(s.get("mood", ""), mood) for s in genre_songs):
            conflicts.append(Conflict(
                "genre_mood_absent",
                f"No '{genre}' song has a '{mood}' mood in the catalog.",
            ))

    # 4. Acoustic preference the genre's songs cannot meet.
    if genre_songs and isinstance(likes_acoustic, bool):
        if likes_acoustic and not any(s["acousticness"] >= ACOUSTIC_CUTOFF for s in genre_songs):
            conflicts.append(Conflict(
                "acoustic_unavailable",
                f"You prefer acoustic songs, but no '{genre}' song in the catalog is acoustic.",
            ))
        elif not likes_acoustic and not any(s["acousticness"] <= ACOUSTIC_CUTOFF for s in genre_songs):
            conflicts.append(Conflict(
                "acoustic_unavailable",
                f"You prefer non-acoustic songs, but every '{genre}' song in the catalog is acoustic.",
            ))

    # 5. No single song satisfies every stated preference at once.
    has_any_pref = bool(genre) or bool(mood) or energy is not None or isinstance(likes_acoustic, bool)
    if has_any_pref and not any(
        _satisfies_all(s, genre, mood, energy, likes_acoustic) for s in songs
    ):
        conflicts.append(Conflict(
            "no_single_song_satisfies_all",
            "No single song matches all of your preferences at once; "
            "your recommendations will be partial matches.",
        ))

    return conflicts
