from dataclasses import asdict

from src.recommender import Song, UserProfile, Recommender, score_song, recommend_songs

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


# ---------------------------------------------------------------------------
# Direct unit tests for the functional core (score_song / recommend_songs).
# ---------------------------------------------------------------------------

def make_song(**overrides) -> dict:
    base = {
        "id": 1, "title": "Track", "artist": "Artist",
        "genre": "pop", "mood": "happy",
        "energy": 0.8, "tempo_bpm": 120.0, "valence": 0.7,
        "danceability": 0.8, "acousticness": 0.2,
    }
    base.update(overrides)
    return base


def test_score_song_genre_match_adds_three():
    song = make_song(genre="pop")
    score, _ = score_song({"genre": "pop"}, song)
    assert score == 3.0


def test_score_song_mood_match_adds_two():
    song = make_song(mood="happy")
    score, _ = score_song({"mood": "happy"}, song)
    assert score == 2.0


def test_score_song_is_case_insensitive():
    song = make_song(genre="edm")
    score, _ = score_song({"genre": "EDM"}, song)
    assert score == 3.0


def test_score_song_energy_rewards_closeness_not_magnitude():
    # target 0.80: a song AT 0.80 should beat a higher-energy 0.93 song.
    close = make_song(energy=0.80)
    louder = make_song(energy=0.93)
    close_score, _ = score_song({"target_energy": 0.80}, close)
    louder_score, _ = score_song({"target_energy": 0.80}, louder)
    assert close_score > louder_score


def test_score_song_acoustic_preference_direction():
    acoustic = make_song(acousticness=0.9)
    # likes_acoustic True rewards high acousticness; False rewards low.
    likes, _ = score_song({"likes_acoustic": True}, acoustic)
    dislikes, _ = score_song({"likes_acoustic": False}, acoustic)
    assert likes > dislikes


def test_recommend_songs_ranks_highest_first():
    songs = [
        make_song(id=1, genre="rock"),          # no genre match
        make_song(id=2, genre="pop"),           # genre match
    ]
    ranked = recommend_songs({"genre": "pop"}, songs, k=2)
    assert ranked[0][0]["id"] == 2
    assert ranked[0][1] >= ranked[1][1]


def test_recommend_songs_respects_k():
    songs = [make_song(id=i) for i in range(1, 6)]
    assert len(recommend_songs({"genre": "pop"}, songs, k=3)) == 3


def test_recommend_songs_empty_catalog_returns_empty():
    assert recommend_songs({"genre": "pop"}, [], k=5) == []


def test_recommend_songs_does_not_mutate_input():
    songs = [make_song(id=1, genre="rock"), make_song(id=2, genre="pop")]
    original_order = [s["id"] for s in songs]
    recommend_songs({"genre": "pop"}, songs, k=2)
    assert [s["id"] for s in songs] == original_order


# ---------------------------------------------------------------------------
# OOP <-> functional parity (Step 8 wiring).
# ---------------------------------------------------------------------------

def test_oop_recommend_matches_functional_order():
    songs = [
        Song(id=1, title="Pop A", artist="X", genre="pop", mood="happy",
             energy=0.8, tempo_bpm=120, valence=0.9, danceability=0.8, acousticness=0.2),
        Song(id=2, title="Rock B", artist="Y", genre="rock", mood="intense",
             energy=0.9, tempo_bpm=150, valence=0.4, danceability=0.6, acousticness=0.1),
        Song(id=3, title="Lofi C", artist="Z", genre="lofi", mood="chill",
             energy=0.3, tempo_bpm=80, valence=0.6, danceability=0.5, acousticness=0.9),
    ]
    user = UserProfile(favorite_genre="pop", favorite_mood="happy",
                       target_energy=0.8, likes_acoustic=False)

    oop_titles = [s.title for s in Recommender(songs).recommend(user, k=3)]

    prefs = {"genre": "pop", "mood": "happy", "target_energy": 0.8, "likes_acoustic": False}
    fun_titles = [s["title"] for s, _, _ in recommend_songs(prefs, [asdict(s) for s in songs], k=3)]

    assert oop_titles == fun_titles


def test_oop_recommend_respects_k_and_returns_song_objects():
    rec = make_small_recommender()
    user = UserProfile(favorite_genre="pop", favorite_mood="happy",
                       target_energy=0.8, likes_acoustic=False)
    results = rec.recommend(user, k=1)
    assert len(results) == 1
    assert isinstance(results[0], Song)
