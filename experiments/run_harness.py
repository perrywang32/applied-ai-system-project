"""
End-to-end test harness for the Music Recommender.

Runs the COMPLETE system (validation -> conflicts -> recommend -> confidence ->
fallback -> evaluation) against a predefined set of user profiles covering:

  1. a normal profile with a strong expected match,
  2. a profile with partial matches,
  3. a conflicting / difficult profile,
  4. invalid input,
  5. a profile that triggers fallback behavior,
  6. a boundary energy value.

Each case has clearly defined PASS/FAIL criteria. Output is fully deterministic
(no timestamps or randomness) and is printed and saved to a text file so it can
be copied into the README. No web interface is required.

Run from the project root:  python -m experiments.run_harness
"""

from typing import Callable, Dict, List, Optional, Tuple

from src.confidence import preference_breakdown, score_confidence
from src.conflicts import detect_conflicts
from src.evaluation import evaluate_profile
from src.fallback import build_fallback
from src.recommender import load_songs, recommend_songs
from src.validation import (
    ValidationError,
    validate_dataset,
    validate_top_k,
    validate_user_prefs,
)

WIDTH = 64
K = 5
REPORT_PATH = "experiments/harness_report.txt"


# --- Case definitions ------------------------------------------------------
# Each valid case: (name, prefs, criteria_description, criteria_fn).
# criteria_fn(confidence, fallback, conflicts, recommendations, evaluation) -> bool

ValidCriteria = Callable[[object, object, list, list, object], bool]

VALID_CASES: List[Tuple[str, Dict, str, ValidCriteria]] = [
    (
        "Normal strong match",
        {"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False},
        "confidence label is High and fallback is NOT used",
        lambda c, f, cf, r, ev: c.label == "High" and not f.triggered,
    ),
    (
        "Partial match",
        {"genre": "pop", "mood": "happy", "target_energy": 0.70, "likes_acoustic": True},
        "confidence label is Medium and fallback is NOT used",
        lambda c, f, cf, r, ev: c.label == "Medium" and not f.triggered,
    ),
    (
        "Conflicting / difficult",
        {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True},
        "at least one conflict is detected and confidence label is Low",
        lambda c, f, cf, r, ev: len(cf) > 0 and c.label == "Low",
    ),
    (
        "Fallback trigger",
        {"genre": "jazz", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False},
        "fallback IS activated",
        lambda c, f, cf, r, ev: f.triggered is True,
    ),
    (
        "Boundary energy value (1.0)",
        {"genre": "edm", "mood": "energetic", "target_energy": 1.0, "likes_acoustic": False},
        "boundary value is accepted and recommendations are returned",
        lambda c, f, cf, r, ev: len(r) > 0,
    ),
]

# Invalid case: (name, prefs, criteria_description). PASS if validation rejects it.
INVALID_CASE = (
    "Invalid input (energy out of range)",
    {"genre": "pop", "mood": "happy", "energy": 1.5},
    "input is rejected by validation with a clear error",
)


# --- Formatting helpers ----------------------------------------------------

def _fmt_prefs(prefs: Dict) -> str:
    order = ["genre", "favorite_genre", "mood", "favorite_mood",
             "target_energy", "energy", "likes_acoustic"]
    parts = [f"{key}={prefs[key]}" for key in order if key in prefs]
    return ", ".join(parts)


def _fmt_metrics(ev) -> str:
    return (f"genre={ev.genre_match_rate} mood={ev.mood_match_rate} "
            f"energy_err={ev.average_energy_error} acoustic={ev.acoustic_match_rate} "
            f"attrs={ev.attributes_satisfied_pct}")


def _warnings(conflicts: list, confidence) -> List[str]:
    warnings = [f"[{c.code}] {c.message}" for c in conflicts]
    if confidence.label == "Low":
        warnings.append("[low_confidence] recommendations may not match you well")
    return warnings


# --- Case runners ----------------------------------------------------------

def _run_valid_case(name, prefs, criteria_desc, criteria_fn, songs, index) -> Tuple[List[str], Optional[float], bool, bool]:
    lines: List[str] = []
    lines.append("=" * WIDTH)
    lines.append(f"CASE {index}: {name}")
    lines.append("=" * WIDTH)
    lines.append(f"Input profile: {_fmt_prefs(prefs)}")
    lines.append(f"Criteria: {criteria_desc}")

    # Run the complete pipeline.
    normalized = validate_user_prefs(prefs)
    k = validate_top_k(K)
    conflicts = detect_conflicts(normalized, songs)
    recommendations = recommend_songs(normalized, songs, k=k)
    confidence = score_confidence(normalized, recommendations, conflicts)
    fallback = build_fallback(normalized, recommendations, confidence)
    evaluation = evaluate_profile(name, normalized, songs, k=k)

    lines.append("")
    lines.append("Top recommendations:")
    for rank, (song, score, _reasons) in enumerate(recommendations, start=1):
        lines.append(f"  {rank}. {song['title']} - {song['artist']} (score {score:.2f})")

    top_song = recommendations[0][0] if recommendations else None
    matched, unmatched = preference_breakdown(normalized, top_song) if top_song else ([], [])
    lines.append("Top match preferences:")
    lines.append(f"  Matched: {', '.join(matched) if matched else '(none)'}")
    lines.append(f"  Did not match: {', '.join(unmatched) if unmatched else '(none)'}")

    lines.append(f"Confidence: {confidence.value:.2f} ({confidence.label})")

    warnings = _warnings(conflicts, confidence)
    lines.append("Warnings:")
    if warnings:
        for w in warnings:
            lines.append(f"  - {w}")
    else:
        lines.append("  (none)")

    lines.append(f"Fallback used: {'yes' if fallback.triggered else 'no'}")
    lines.append(f"Evaluation metrics: {_fmt_metrics(evaluation)}")

    passed = bool(criteria_fn(confidence, fallback, conflicts, recommendations, evaluation))
    lines.append(f"Result: {'PASS' if passed else 'FAIL'}")
    lines.append("")

    return lines, confidence.value, fallback.triggered, passed


def _run_invalid_case(name, prefs, criteria_desc, index) -> Tuple[List[str], bool]:
    lines: List[str] = []
    lines.append("=" * WIDTH)
    lines.append(f"CASE {index}: {name}")
    lines.append("=" * WIDTH)
    lines.append(f"Input profile: {_fmt_prefs(prefs)}")
    lines.append(f"Criteria: {criteria_desc}")

    try:
        validate_user_prefs(prefs)
        rejected = False
        detail = "input was accepted (should have been rejected)"
    except ValidationError as error:
        rejected = True
        detail = f"REJECTED - {error}"

    lines.append(f"Validation: {detail}")
    lines.append(f"Result: {'PASS' if rejected else 'FAIL'}")
    lines.append("")
    return lines, rejected


# --- Orchestration ---------------------------------------------------------

def run() -> Tuple[str, Dict]:
    """Run all cases and return (report_text, summary_dict). Deterministic."""
    songs = load_songs("data/songs.csv")
    validate_dataset(songs)

    report: List[str] = []
    report.append("MUSIC RECOMMENDER - END-TO-END TEST HARNESS")
    report.append("")

    passed = 0
    confidences: List[float] = []
    fallback_count = 0
    index = 0

    # Cases 1, 2, 3 (valid), then 4 (invalid), then 5, 6 (valid) to match the
    # required ordering of the six cases.
    ordered = [
        ("valid", VALID_CASES[0]),   # 1 normal
        ("valid", VALID_CASES[1]),   # 2 partial
        ("valid", VALID_CASES[2]),   # 3 conflicting
        ("invalid", INVALID_CASE),   # 4 invalid
        ("valid", VALID_CASES[3]),   # 5 fallback
        ("valid", VALID_CASES[4]),   # 6 boundary
    ]

    for kind, case in ordered:
        index += 1
        if kind == "valid":
            name, prefs, desc, fn = case
            lines, conf, fb, ok = _run_valid_case(name, prefs, desc, fn, songs, index)
            report.extend(lines)
            confidences.append(conf)
            fallback_count += int(fb)
            passed += int(ok)
        else:
            name, prefs, desc = case
            lines, ok = _run_invalid_case(name, prefs, desc, index)
            report.extend(lines)
            passed += int(ok)

    total = index
    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    report.append("=" * WIDTH)
    report.append("SUMMARY")
    report.append("=" * WIDTH)
    report.append(f"Total cases:        {total}")
    report.append(f"Passed:             {passed}")
    report.append(f"Failed:             {total - passed}")
    report.append(f"Average confidence: {avg_conf:.2f}  (over {len(confidences)} valid cases)")
    report.append(f"Fallback cases:     {fallback_count}")
    report.append("=" * WIDTH)

    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "average_confidence": avg_conf,
        "fallback_cases": fallback_count,
    }
    return "\n".join(report), summary


def main() -> None:
    report_text, _summary = run()
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text + "\n")
    print(report_text)
    print(f"\nSaved report to {REPORT_PATH}")


if __name__ == "__main__":
    main()
