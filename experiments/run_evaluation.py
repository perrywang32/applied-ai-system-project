"""
Evaluation harness: runs the real recommender over several diverse profiles,
computes deterministic quality metrics, prints a report, and saves it to
experiments/evaluation_results.md as execution evidence.

Run from the project root:  python -m experiments.run_evaluation
"""

from dataclasses import asdict

from src.evaluation import evaluate_profiles
from src.recommender import load_songs

# (label, prefs) — the same diverse profiles used elsewhere in the project.
PROFILES = [
    ("High-energy EDM",
     {"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False}),
    ("Chill lo-fi",
     {"genre": "lofi", "mood": "chill", "target_energy": 0.35, "likes_acoustic": True}),
    ("Rock / intense",
     {"genre": "rock", "mood": "intense", "target_energy": 0.90, "likes_acoustic": False}),
    ("Adversarial / conflicting",
     {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}),
]

RESULTS_PATH = "experiments/evaluation_results.md"


def _per_profile_table(summary) -> str:
    header = (
        "| Profile | Conf | Label | Genre | Mood | EnergyErr | Acoustic | Attrs | Fallback |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    rows = []
    for p in summary.per_profile:
        rows.append(
            f"| {p.label} | {p.confidence:.2f} | {p.confidence_label} | "
            f"{p.genre_match_rate} | {p.mood_match_rate} | {p.average_energy_error} | "
            f"{p.acoustic_match_rate} | {p.attributes_satisfied_pct} | "
            f"{'yes' if p.fallback_triggered else 'no'} |"
        )
    return "\n".join([header, *rows])


def main() -> None:
    songs = load_songs("data/songs.csv")
    summary = evaluate_profiles(PROFILES, songs, k=5)

    report = (
        "# Evaluation Results\n\n"
        "Deterministic metrics from the real recommender pipeline "
        "(`python -m experiments.run_evaluation`).\n\n"
        "## Per-profile\n\n"
        + _per_profile_table(summary)
        + "\n\n## Aggregate\n\n```\n"
        + summary.summary_text()
        + "\n```\n"
    )

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(summary.summary_text())
    print(f"\nSaved full report to {RESULTS_PATH}")
    # asdict() shows the structured result is a plain dict when needed.
    _ = [asdict(p) for p in summary.per_profile]


if __name__ == "__main__":
    main()
