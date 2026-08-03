"""
Focused tests for input validation (src/validation.py) and the validating
loader (load_songs). Covers valid inputs plus every required failure case.
"""

import pytest

from src.recommender import load_songs
from src.validation import (
    DatasetValidationError,
    ParameterValidationError,
    ProfileValidationError,
    validate_dataset,
    validate_top_k,
    validate_user_prefs,
)


# --- Reusable fixtures -----------------------------------------------------

def valid_prefs() -> dict:
    return {"genre": "pop", "mood": "happy", "energy": 0.8}


def one_song(**overrides) -> dict:
    song = {
        "id": 1,
        "title": "Test Track",
        "artist": "Tester",
        "genre": "pop",
        "mood": "happy",
        "energy": 0.8,
        "tempo_bpm": 120.0,
        "valence": 0.7,
        "danceability": 0.8,
        "acousticness": 0.2,
    }
    song.update(overrides)
    return song


CSV_HEADER = (
    "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness"
)


# === Profile validation ====================================================

def test_valid_prefs_pass_and_are_normalized():
    result = validate_user_prefs({"genre": "  Pop ", "mood": "happy", "energy": 0.8})
    assert result["genre"] == "Pop"          # trimmed
    assert result["energy"] == 0.8

def test_valid_prefs_accept_alias_keys():
    result = validate_user_prefs(
        {"favorite_genre": "edm", "favorite_mood": "energetic",
         "target_energy": 0.95, "likes_acoustic": False}
    )
    assert result["target_energy"] == 0.95

def test_missing_genre_field_is_rejected():
    with pytest.raises(ProfileValidationError):
        validate_user_prefs({"mood": "happy", "energy": 0.8})

def test_missing_mood_field_is_rejected():
    with pytest.raises(ProfileValidationError):
        validate_user_prefs({"genre": "pop", "energy": 0.8})

def test_missing_energy_field_is_rejected():
    with pytest.raises(ProfileValidationError):
        validate_user_prefs({"genre": "pop", "mood": "happy"})

@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_genre_is_rejected(blank):
    with pytest.raises(ProfileValidationError):
        validate_user_prefs({"genre": blank, "mood": "happy", "energy": 0.8})

@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_mood_is_rejected(blank):
    with pytest.raises(ProfileValidationError):
        validate_user_prefs({"genre": "pop", "mood": blank, "energy": 0.8})

@pytest.mark.parametrize("bad_energy", ["high", None, True])
def test_invalid_energy_values_are_rejected(bad_energy):
    with pytest.raises(ProfileValidationError):
        validate_user_prefs({"genre": "pop", "mood": "happy", "energy": bad_energy})

@pytest.mark.parametrize("out_of_range", [-0.1, 1.5, 42])
def test_energy_out_of_range_is_rejected(out_of_range):
    with pytest.raises(ProfileValidationError):
        validate_user_prefs({"genre": "pop", "mood": "happy", "energy": out_of_range})

def test_non_boolean_likes_acoustic_is_rejected():
    with pytest.raises(ProfileValidationError):
        validate_user_prefs(
            {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": "yes"}
        )


# === Top-k validation ======================================================

def test_valid_top_k_passes():
    assert validate_top_k(5) == 5

@pytest.mark.parametrize("bad_k", [0, -1, "5", 2.5, True, None])
def test_invalid_top_k_is_rejected(bad_k):
    with pytest.raises(ParameterValidationError):
        validate_top_k(bad_k)


# === Dataset validation (in-memory) ========================================

def test_valid_dataset_passes():
    songs = [one_song(id=1), one_song(id=2, title="Another")]
    assert validate_dataset(songs) == songs

def test_empty_dataset_is_rejected():
    with pytest.raises(DatasetValidationError):
        validate_dataset([])

def test_missing_required_column_is_rejected():
    broken = one_song()
    del broken["energy"]
    with pytest.raises(DatasetValidationError):
        validate_dataset([broken])

def test_non_numeric_song_value_is_rejected():
    with pytest.raises(DatasetValidationError):
        validate_dataset([one_song(energy="loud")])

def test_out_of_range_song_value_is_rejected():
    with pytest.raises(DatasetValidationError):
        validate_dataset([one_song(acousticness=1.4)])


# === Dataset validation (via load_songs on real CSV files) =================

def _write_csv(tmp_path, rows):
    path = tmp_path / "songs.csv"
    path.write_text("\n".join([CSV_HEADER, *rows]) + "\n", encoding="utf-8")
    return str(path)

def test_load_songs_reads_valid_csv(tmp_path):
    path = _write_csv(tmp_path, ["1,Sunrise,Neon,pop,happy,0.82,118,0.84,0.79,0.18"])
    songs = load_songs(path)
    assert len(songs) == 1
    assert songs[0]["energy"] == 0.82

def test_load_songs_rejects_malformed_number(tmp_path):
    path = _write_csv(tmp_path, ["1,Sunrise,Neon,pop,happy,loud,118,0.84,0.79,0.18"])
    with pytest.raises(DatasetValidationError):
        load_songs(path)

def test_load_songs_rejects_missing_column(tmp_path):
    # Header without the 'acousticness' column.
    bad_header = "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability"
    path = tmp_path / "songs.csv"
    path.write_text(bad_header + "\n1,Sunrise,Neon,pop,happy,0.82,118,0.84,0.79\n",
                    encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load_songs(str(path))
