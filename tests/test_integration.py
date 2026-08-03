"""
Full-stack integration tests.

These run one complete path through every reliability layer on the REAL catalog
(validation -> conflicts -> recommend -> confidence -> fallback -> evaluation),
proving the layers cooperate end to end for both a coherent and an adversarial
profile.
"""

from src.confidence import score_confidence
from src.conflicts import detect_conflicts
from src.evaluation import evaluate_profile
from src.fallback import build_fallback
from src.recommender import load_songs, recommend_songs
from src.validation import validate_dataset, validate_top_k, validate_user_prefs


def _run_pipeline(prefs, k=5):
    songs = load_songs("data/songs.csv")
    validate_dataset(songs)
    prefs = validate_user_prefs(prefs)
    k = validate_top_k(k)
    conflicts = detect_conflicts(prefs, songs)
    recommendations = recommend_songs(prefs, songs, k=k)
    confidence = score_confidence(prefs, recommendations, conflicts)
    fallback = build_fallback(prefs, recommendations, confidence)
    evaluation = evaluate_profile("integration", prefs, songs, k=k)
    return conflicts, recommendations, confidence, fallback, evaluation


def test_coherent_profile_end_to_end():
    conflicts, recs, confidence, fallback, evaluation = _run_pipeline(
        {"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False}
    )
    assert conflicts == []
    assert len(recs) == 5
    assert confidence.label == "High"
    assert fallback.triggered is False
    assert evaluation.genre_match_rate == 1.0        # top-5 are all EDM


def test_adversarial_profile_end_to_end():
    conflicts, recs, confidence, fallback, evaluation = _run_pipeline(
        {"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}
    )
    assert len(conflicts) > 0
    assert len(recs) == 5                              # still returns results
    assert confidence.label == "Low"
    assert fallback.triggered is True
    assert evaluation.is_low_confidence is True
