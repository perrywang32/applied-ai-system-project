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
from src.fallback import build_fallback
from src.logging_config import get_logger
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


def print_fallback(fallback) -> None:
    """When confidence is low, explain that and show the closest alternatives."""
    if not fallback.triggered:
        return
    print()
    print("*" * WIDTH)
    print("  NO STRONG MATCH FOUND".ljust(WIDTH))
    print("*" * WIDTH)
    print(f"  {fallback.message}")
    print(f"  (confidence {fallback.confidence:.2f} is below the "
          f"{fallback.threshold:.2f} threshold)")
    if fallback.alternatives:
        print()
        print("  Closest available alternatives:")
        for rank, alt in enumerate(fallback.alternatives, start=1):
            print(f"    {rank}. {alt.title} - {alt.artist} (score {alt.score:.2f})")
            if alt.matched:
                print(f"       Matched: {', '.join(alt.matched)}")
            if alt.unmatched:
                print(f"       Did not match: {', '.join(alt.unmatched)}")
    print("*" * WIDTH)


def main() -> None:
    # Detailed technical events go to logs/recommender.log; the user only sees
    # the clean console output produced by the print_* helpers.
    logger = get_logger()
    logger.info("Application startup")

    # The whole workflow is guarded: bad input (dataset or profile) is reported
    # as a clear message and stops the run before scoring happens; anything
    # unexpected is logged with a traceback instead of surfacing raw to the user.
    try:
        data_path = "data/songs.csv"
        songs = load_songs(data_path)
        validate_dataset(songs)                      # dataset must be usable
        logger.info("Dataset loaded: %d songs from %s", len(songs), data_path)

        # Starter example profile
        user_prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
        k = 5

        user_prefs = validate_user_prefs(user_prefs)  # profile must be well-formed
        k = validate_top_k(k)                          # top-k must be valid

        # Warn (but don't stop) when the profile is hard to satisfy in this catalog.
        conflicts = detect_conflicts(user_prefs, songs)
        if conflicts:
            logger.warning("Profile conflicts detected: %d", len(conflicts))
            for conflict in conflicts:
                logger.warning("Conflict [%s]: %s", conflict.code, conflict.message)
        print_conflicts(conflicts)

        logger.info("Evaluating %d songs against the profile", len(songs))
        recommendations = recommend_songs(user_prefs, songs, k=k)
        logger.info("Recommendation complete: returned %d results", len(recommendations))

        # Confidence combines match quality, separation, coverage, and penalties
        # for conflicts / fallback matches (see src/confidence.py).
        confidence = score_confidence(user_prefs, recommendations, conflicts)
        logger.info("Confidence: %.2f (%s)", confidence.value, confidence.label)

        # If confidence is low, fall back to an honest "closest alternatives"
        # framing (the normal ranked output below is still preserved).
        fallback = build_fallback(user_prefs, recommendations, confidence)
        if fallback.triggered:
            logger.warning(
                "Fallback activated: confidence %.2f below threshold %.2f",
                confidence.value, fallback.threshold,
            )

        print_recommendations(user_prefs, recommendations)
        print_confidence(confidence)
        print_fallback(fallback)
    except ValidationError as error:
        # Expected, user-fixable problem: warn in the log, show a clean message.
        logger.warning("Validation failed: %s", error)
        print(f"\n[Input Error] {error}\n")
        sys.exit(1)
    except Exception:
        # Unexpected: keep the full traceback in the log, show a calm message.
        logger.exception("Unexpected error during recommendation")
        print("\n[Error] Something went wrong. See logs/recommender.log for details.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
