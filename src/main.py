"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import sys

from src.confidence import score_confidence
from src.conflicts import detect_conflicts
from src.recommender import load_songs, recommend_songs
from src.validation import (
    ValidationError,
    validate_dataset,
    validate_top_k,
    validate_user_prefs,
)

# Width of the divider lines. Kept as a constant so the layout is easy to tweak.
WIDTH = 60


def print_recommendations(user_prefs: dict, recommendations: list) -> None:
    """Print the ranked recommendations in a clean, readable layout."""
    print()
    print("=" * WIDTH)
    print("  TOP MUSIC RECOMMENDATIONS".ljust(WIDTH))
    print("=" * WIDTH)

    # Show which preferences produced these results.
    profile = "  |  ".join(f"{key}: {value}" for key, value in user_prefs.items())
    print(f"For profile -> {profile}")
    print("=" * WIDTH)

    if not recommendations:
        print("\n  No matching songs found.\n")
        print("=" * WIDTH)
        return

    for rank, (song, score, reasons) in enumerate(recommendations, start=1):
        print()
        print(f"  #{rank}  {song['title']}")
        print(f"      Artist : {song['artist']}")
        print(f"      Score  : {score:.2f}")
        print(f"      Reasons:")
        for reason in reasons:
            print(f"        - {reason}")
        print("-" * WIDTH)


def print_conflicts(conflicts: list) -> None:
    """Print any profile-conflict warnings above the recommendations."""
    if not conflicts:
        return
    print()
    print("!" * WIDTH)
    print("  PROFILE CONFLICT WARNINGS".ljust(WIDTH))
    print("!" * WIDTH)
    print("  These preferences are hard to satisfy with the current catalog.")
    print("  Recommendations are still shown below, but may be partial matches.")
    for conflict in conflicts:
        print(f"    - {conflict.message}")
    print("!" * WIDTH)


def print_confidence(confidence) -> None:
    """Show the confidence score, its per-preference reasons, and a Low warning.

    Uses a plain '-' rather than an em dash so the line renders cleanly on the
    Windows console.
    """
    print()
    print("=" * WIDTH)
    print(f"  Confidence: {confidence.value:.2f} - {confidence.label}")
    print()
    print("  Reason:")
    for reason in confidence.reasons:
        print(f"    - {reason}")
    if confidence.label == "Low":
        print()
        print("  [Low confidence] These recommendations may not match you well.")
        print("  Try broadening your preferences or review the warnings above.")
    print("=" * WIDTH)


def main() -> None:
    # The whole workflow is guarded: any bad input (dataset or profile) is
    # reported as a clear message and stops the run before scoring happens,
    # instead of surfacing a raw traceback.
    try:
        songs = load_songs("data/songs.csv")
        validate_dataset(songs)                      # dataset must be usable

        # Starter example profile
        user_prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
        k = 5

        user_prefs = validate_user_prefs(user_prefs)  # profile must be well-formed
        k = validate_top_k(k)                          # top-k must be valid

        # Warn (but don't stop) when the profile is hard to satisfy in this catalog.
        conflicts = detect_conflicts(user_prefs, songs)
        print_conflicts(conflicts)

        recommendations = recommend_songs(user_prefs, songs, k=k)

        # Confidence combines match quality, separation, coverage, and penalties
        # for conflicts / fallback matches (see src/confidence.py).
        confidence = score_confidence(user_prefs, recommendations, conflicts)

        print_recommendations(user_prefs, recommendations)
        print_confidence(confidence)
    except ValidationError as error:
        print(f"\n[Input Error] {error}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
