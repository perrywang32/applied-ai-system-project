# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

This project implements a simple music recommendation system that suggests songs based on a user's preferences. Each song is scored using features such as genre, mood, energy, and acousticness, then ranked from highest to lowest score. The project demonstrates how recommendation systems use weighted features to personalize suggestions while also highlighting the limitations and potential biases of rule-based recommenders.

---

## How The System Works

Explain your design in plain language.

Some prompts to answer:

- What features does each `Song` use in your system
  - For example: genre, mood, energy, tempo
- What information does your `UserProfile` store
- How does your `Recommender` compute a score for each song
- How do you choose which songs to recommend

You can include a simple diagram or bullet list if helpful.

My music recommendation system compares a user's preferences with the attributes of every song in the dataset. Each Song contains features such as genre, mood, energy, and acousticness. The UserProfile stores the user's favorite genre, favorite mood, target energy level, and acousticness preference. The recommender reads every song from songs.csv and calculates a score based on how closely each song matches the user's preferences. Genre is weighted the most because it represents the overall style of music, followed by mood. Energy is scored using a closeness formula, so songs with energy levels nearest the user's target receive more points. Acousticness is used as a smaller preference to help break ties. After every song is scored, the system sorts the songs from highest to lowest score and recommends the top results. This is a simplified version of how streaming services personalize recommendations for users.

Algorithm Recipe
* Read the user's preferences.
* Load every song from songs.csv.
* Compare the song's genre with the user's favorite genre.
* Compare the song's mood with the user's favorite mood.
* Award points based on how close the song's energy is to     the user's target energy.
* Award points based on whether the song matches the user's acousticness preference.
* Add the points together to calculate the song's total score.
* Repeat for every song.
* Sort all songs by score.
* Recommend the Top K highest-scoring songs.

Potential Biases

This recommender may over-prioritize genre, causing songs from other genres that closely match the user's mood or energy to receive lower scores. It also depends on manually chosen weights, which may not reflect every user's listening habits. Real recommendation systems reduce these biases by learning from large amounts of user behavior and continuously adjusting their models.
---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows
   ```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Recommendation Output

Running `python -m src.main` with the profile `genre=pop, mood=happy, energy=0.8`
against the 24-song catalog produces:

```
Loaded 24 songs from data/songs.csv

============================================================
  TOP MUSIC RECOMMENDATIONS
============================================================
For profile -> genre: pop  |  mood: happy  |  energy: 0.8
============================================================

  #1  Sunrise City
      Artist : Neon Echo
      Score  : 6.96
      Reasons:
        - Genre 'pop' matches your favorite (+3.0)
        - Mood 'happy' matches your favorite (+2.0)
        - Energy 0.82 vs target 0.80 (+1.96)
------------------------------------------------------------

  #2  Gym Hero
      Artist : Max Pulse
      Score  : 4.74
      Reasons:
        - Genre 'pop' matches your favorite (+3.0)
        - Mood 'intense' is not your favorite 'happy' (+0.0)
        - Energy 0.93 vs target 0.80 (+1.74)
------------------------------------------------------------

  #3  Rooftop Lights
      Artist : Indigo Parade
      Score  : 3.92
      Reasons:
        - Genre 'indie pop' is not your favorite 'pop' (+0.0)
        - Mood 'happy' matches your favorite (+2.0)
        - Energy 0.76 vs target 0.80 (+1.92)
------------------------------------------------------------

  #4  Basement Groove
      Artist : Funk Factory
      Score  : 2.00
      Reasons:
        - Genre 'funk' is not your favorite 'pop' (+0.0)
        - Mood 'playful' is not your favorite 'happy' (+0.0)
        - Energy 0.80 vs target 0.80 (+2.00)
------------------------------------------------------------

  #5  Afterglow Skies
      Artist : Illenium
      Score  : 1.96
      Reasons:
        - Genre 'edm' is not your favorite 'pop' (+0.0)
        - Mood 'uplifting' is not your favorite 'happy' (+0.0)
        - Energy 0.78 vs target 0.80 (+1.96)
------------------------------------------------------------
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or demo video link here -->

---

## Recommendation Confidence

Every run reports a **confidence** value between **0 and 1** with a label of
**High**, **Medium**, or **Low**. Confidence answers a different question than the
raw score: the score says *how well the top song matched*, while confidence says
*how much you should trust the result*. We deliberately do **not** reuse the raw
score as confidence — a song can score highly while barely beating the runner-up
or satisfying only some of your preferences.

Confidence is built from evidence we already have, each scaled to 0–1:

| Piece | Meaning | How it's computed |
|---|---|---|
| **Match quality** | How good the top match is | `top_score / 8.0` (8.0 is the max possible score) |
| **Separation** | How clearly #1 beats #2 | `min(1, (score1 − score2) / 2.0)` (a 2-point lead = full) |
| **Coverage** | How many stated preferences the top song meets | `satisfied / requested` |

These are combined with fixed weights, then reduced by penalties:

```
base       = 0.50 * match_quality + 0.20 * separation + 0.30 * coverage
confidence = base
             * 0.85   if the top song is a FALLBACK match (not all prefs met)
             * 0.75   if a profile CONFLICT was detected

label:  confidence >= 0.80 -> High     (near-perfect match)
        confidence >= 0.50 -> Medium   (a preference or two missed)
        otherwise          -> Low
```

Because every input is fixed data, the same profile and catalog always produce
the **same** confidence (it is deterministic). The app prints the confidence
value, its label, and a plain-English reason per preference. When confidence is
**Low**, it also prints a warning suggesting you broaden your preferences.

A reasonable partial-match result looks like this:

```
Confidence: 0.74 - Medium

Reason:
  - Genre matched
  - Mood matched
  - Energy difference was 0.12
  - Acoustic preference did not match
```

Here genre and mood matched and the energy was close (difference 0.12), but the
acoustic preference was missed, so the top song is a *fallback* rather than an
exact match — which pulls confidence down into the Medium band.

### Fallback for weak matches

When confidence falls into the **Low** band (below the `0.50` threshold), the
top result is not a strong, complete match. Instead of presenting a weak match
as if it were perfect, the app adds a **"NO STRONG MATCH FOUND"** section that:

- states plainly that no strong complete match was found,
- lists the **closest available alternatives** (the top of the normal ranking),
- explains, per alternative, which preferences **matched** and which **did not**.

The normal ranked recommendations are still shown — fallback only adds an honest
framing on top of them, and never returns an empty result when alternatives
exist. Example (adversarial `metal / chill / 0.10 / acoustic` profile):

```
************************************************************
  NO STRONG MATCH FOUND
************************************************************
  No strong complete match was found for your preferences. Showing the
  closest available alternatives instead.
  (confidence 0.29 is below the 0.50 threshold)

  Closest available alternatives:
    1. Spacewalk Thoughts - Orbit Bloom (score 4.56)
       Matched: Mood matched, Acoustic preference matched
       Did not match: Genre did not match, Energy difference was 0.18
    ...
************************************************************
```

---

## Multi-Profile Testing

To stress-test the scorer beyond the single starter profile, I ran it against
four deliberately different taste profiles. Each is a plain `user_prefs` dict
passed to `recommend_songs(prefs, songs, k=5)`. All output below is real
terminal output captured by running `python run_profiles.py` from the project
root.

| Profile | `user_prefs` | Why it's useful for testing |
|---|---|---|
| **High-energy EDM** | `{"genre": "edm", "mood": "energetic", "target_energy": 0.95, "likes_acoustic": False}` | A "happy path" where every signal agrees. Confirms genre + mood + high energy + non-acoustic all stack to push true EDM tracks to the top. |
| **Chill lo-fi** | `{"genre": "lofi", "mood": "chill", "target_energy": 0.35, "likes_acoustic": True}` | The opposite end of the energy/acoustic spectrum. Verifies the energy-*closeness* and acousticness terms reward calm, acoustic songs rather than loud ones — i.e. the scorer isn't secretly biased toward high energy. |
| **Rock / intense** | `{"genre": "rock", "mood": "intense", "target_energy": 0.90, "likes_acoustic": False}` | High-energy but *non-electronic*. Checks that the scorer separates rock from EDM even though both are loud and fast, and shows how a small genre catalog (one rock song) affects ranking. |
| **Adversarial / conflicting** | `{"genre": "metal", "mood": "chill", "target_energy": 0.10, "likes_acoustic": True}` | An edge case where every signal fights the others: the favorite genre (metal) is loud, fast, and non-acoustic, yet the user asks for a chill mood, near-zero energy, and acoustic songs. Designed to expose weaknesses in the scoring logic. |

### Profile 1 — High-energy EDM

```
############################################################
#  PROFILE: High-energy EDM
############################################################

============================================================
  TOP MUSIC RECOMMENDATIONS
============================================================
For profile -> genre: edm  |  mood: energetic  |  target_energy: 0.95  |  likes_acoustic: False
============================================================

  #1  Neon Warehouse
      Artist : Pulse Divide
      Score  : 7.98
      Reasons:
        - Genre 'edm' matches your favorite (+3.0)
        - Mood 'energetic' matches your favorite (+2.0)
        - Energy 0.95 vs target 0.95 (+2.00)
        - Acousticness 0.02 (you prefer non-acoustic) (+0.98)
------------------------------------------------------------

  #2  Skyline Anthem
      Artist : Martin Garrix
      Score  : 7.90
      Reasons:
        - Genre 'edm' matches your favorite (+3.0)
        - Mood 'energetic' matches your favorite (+2.0)
        - Energy 0.92 vs target 0.95 (+1.94)
        - Acousticness 0.04 (you prefer non-acoustic) (+0.96)
------------------------------------------------------------

  #3  Detonate
      Artist : ISOKNOCK
      Score  : 5.96
      Reasons:
        - Genre 'edm' matches your favorite (+3.0)
        - Mood 'intense' is not your favorite 'energetic' (+0.0)
        - Energy 0.96 vs target 0.95 (+1.98)
        - Acousticness 0.02 (you prefer non-acoustic) (+0.98)
------------------------------------------------------------

  #4  Wreckage
      Artist : Crankdat
      Score  : 5.95
      Reasons:
        - Genre 'edm' matches your favorite (+3.0)
        - Mood 'intense' is not your favorite 'energetic' (+0.0)
        - Energy 0.97 vs target 0.95 (+1.96)
        - Acousticness 0.01 (you prefer non-acoustic) (+0.99)
------------------------------------------------------------

  #5  Afterglow Skies
      Artist : Illenium
      Score  : 5.38
      Reasons:
        - Genre 'edm' matches your favorite (+3.0)
        - Mood 'uplifting' is not your favorite 'energetic' (+0.0)
        - Energy 0.78 vs target 0.95 (+1.66)
        - Acousticness 0.28 (you prefer non-acoustic) (+0.72)
------------------------------------------------------------
```

**What it shows:** the two songs where *all four* signals agree (`Neon Warehouse`, `Skyline Anthem`) score ~7.9 and clearly lead. Below them, the three intense/uplifting EDM tracks lose the +2.0 mood bonus and cluster around 5.4–6.0 — exactly the intended stacking behavior.

### Profile 2 — Chill lo-fi

```
############################################################
#  PROFILE: Chill lo-fi
############################################################

============================================================
  TOP MUSIC RECOMMENDATIONS
============================================================
For profile -> genre: lofi  |  mood: chill  |  target_energy: 0.35  |  likes_acoustic: True
============================================================

  #1  Library Rain
      Artist : Paper Lanterns
      Score  : 7.86
      Reasons:
        - Genre 'lofi' matches your favorite (+3.0)
        - Mood 'chill' matches your favorite (+2.0)
        - Energy 0.35 vs target 0.35 (+2.00)
        - Acousticness 0.86 (you like acoustic) (+0.86)
------------------------------------------------------------

  #2  Midnight Coding
      Artist : LoRoom
      Score  : 7.57
      Reasons:
        - Genre 'lofi' matches your favorite (+3.0)
        - Mood 'chill' matches your favorite (+2.0)
        - Energy 0.42 vs target 0.35 (+1.86)
        - Acousticness 0.71 (you like acoustic) (+0.71)
------------------------------------------------------------

  #3  Focus Flow
      Artist : LoRoom
      Score  : 5.68
      Reasons:
        - Genre 'lofi' matches your favorite (+3.0)
        - Mood 'focused' is not your favorite 'chill' (+0.0)
        - Energy 0.40 vs target 0.35 (+1.90)
        - Acousticness 0.78 (you like acoustic) (+0.78)
------------------------------------------------------------

  #4  Spacewalk Thoughts
      Artist : Orbit Bloom
      Score  : 4.78
      Reasons:
        - Genre 'ambient' is not your favorite 'lofi' (+0.0)
        - Mood 'chill' matches your favorite (+2.0)
        - Energy 0.28 vs target 0.35 (+1.86)
        - Acousticness 0.92 (you like acoustic) (+0.92)
------------------------------------------------------------

  #5  Paper Boats
      Artist : Hazel Grove
      Score  : 2.87
      Reasons:
        - Genre 'folk' is not your favorite 'lofi' (+0.0)
        - Mood 'dreamy' is not your favorite 'chill' (+0.0)
        - Energy 0.33 vs target 0.35 (+1.96)
        - Acousticness 0.91 (you like acoustic) (+0.91)
------------------------------------------------------------
```

**What it shows:** with a *low* target energy, calm songs earn the full energy bonus and loud EDM tracks fall away entirely. This is the key check that the energy term rewards **closeness**, not magnitude. Note `Spacewalk Thoughts` (ambient) cracks the top 5 on mood + energy + acousticness alone, despite scoring 0 on genre — good evidence the non-genre signals actually matter.

### Profile 3 — Rock / intense

```
############################################################
#  PROFILE: Rock / intense
############################################################

============================================================
  TOP MUSIC RECOMMENDATIONS
============================================================
For profile -> genre: rock  |  mood: intense  |  target_energy: 0.9  |  likes_acoustic: False
============================================================

  #1  Storm Runner
      Artist : Voltline
      Score  : 7.88
      Reasons:
        - Genre 'rock' matches your favorite (+3.0)
        - Mood 'intense' matches your favorite (+2.0)
        - Energy 0.91 vs target 0.90 (+1.98)
        - Acousticness 0.10 (you prefer non-acoustic) (+0.90)
------------------------------------------------------------

  #2  Gym Hero
      Artist : Max Pulse
      Score  : 4.89
      Reasons:
        - Genre 'pop' is not your favorite 'rock' (+0.0)
        - Mood 'intense' matches your favorite (+2.0)
        - Energy 0.93 vs target 0.90 (+1.94)
        - Acousticness 0.05 (you prefer non-acoustic) (+0.95)
------------------------------------------------------------

  #3  Detonate
      Artist : ISOKNOCK
      Score  : 4.86
      Reasons:
        - Genre 'edm' is not your favorite 'rock' (+0.0)
        - Mood 'intense' matches your favorite (+2.0)
        - Energy 0.96 vs target 0.90 (+1.88)
        - Acousticness 0.02 (you prefer non-acoustic) (+0.98)
------------------------------------------------------------

  #4  Wreckage
      Artist : Crankdat
      Score  : 4.85
      Reasons:
        - Genre 'edm' is not your favorite 'rock' (+0.0)
        - Mood 'intense' matches your favorite (+2.0)
        - Energy 0.97 vs target 0.90 (+1.86)
        - Acousticness 0.01 (you prefer non-acoustic) (+0.99)
------------------------------------------------------------

  #5  Circuit Breaker
      Artist : Tempo Fault
      Score  : 2.97
      Reasons:
        - Genre 'drum and bass' is not your favorite 'rock' (+0.0)
        - Mood 'tense' is not your favorite 'intense' (+0.0)
        - Energy 0.90 vs target 0.90 (+2.00)
        - Acousticness 0.03 (you prefer non-acoustic) (+0.97)
------------------------------------------------------------
```

**What it shows:** the one true rock song (`Storm Runner`) wins decisively at 7.88. But because the catalog holds only a single rock track, positions #2–#5 fill with high-energy, intense, non-acoustic songs from *other* genres (pop, EDM, drum & bass). This is a realistic small-catalog limitation: the +3.0 genre gap is large enough that no non-rock song can catch `Storm Runner`, but the remaining slots are decided almost entirely by mood and energy.

### Profile 4 — Adversarial / conflicting (edge case)

```
############################################################
#  PROFILE: Adversarial / conflicting
############################################################

============================================================
  TOP MUSIC RECOMMENDATIONS
============================================================
For profile -> genre: metal  |  mood: chill  |  target_energy: 0.1  |  likes_acoustic: True
============================================================

  #1  Spacewalk Thoughts
      Artist : Orbit Bloom
      Score  : 4.56
      Reasons:
        - Genre 'ambient' is not your favorite 'metal' (+0.0)
        - Mood 'chill' matches your favorite (+2.0)
        - Energy 0.28 vs target 0.10 (+1.64)
        - Acousticness 0.92 (you like acoustic) (+0.92)
------------------------------------------------------------

  #2  Library Rain
      Artist : Paper Lanterns
      Score  : 4.36
      Reasons:
        - Genre 'lofi' is not your favorite 'metal' (+0.0)
        - Mood 'chill' matches your favorite (+2.0)
        - Energy 0.35 vs target 0.10 (+1.50)
        - Acousticness 0.86 (you like acoustic) (+0.86)
------------------------------------------------------------

  #3  Midnight Coding
      Artist : LoRoom
      Score  : 4.07
      Reasons:
        - Genre 'lofi' is not your favorite 'metal' (+0.0)
        - Mood 'chill' matches your favorite (+2.0)
        - Energy 0.42 vs target 0.10 (+1.36)
        - Acousticness 0.71 (you like acoustic) (+0.71)
------------------------------------------------------------

  #4  Iron Verdict
      Artist : Ashfall
      Score  : 3.25
      Reasons:
        - Genre 'metal' matches your favorite (+3.0)
        - Mood 'angry' is not your favorite 'chill' (+0.0)
        - Energy 0.98 vs target 0.10 (+0.24)
        - Acousticness 0.01 (you like acoustic) (+0.01)
------------------------------------------------------------

  #5  Chamber of Rain
      Artist : The Chamber Set
      Score  : 2.67
      Reasons:
        - Genre 'classical' is not your favorite 'metal' (+0.0)
        - Mood 'melancholic' is not your favorite 'chill' (+0.0)
        - Energy 0.25 vs target 0.10 (+1.70)
        - Acousticness 0.97 (you like acoustic) (+0.97)
------------------------------------------------------------
```

**What it shows (the weakness this exposes):** the user's *stated* favorite genre is metal, but the only metal song (`Iron Verdict`) lands at **#4**, *below* three songs that don't match the genre at all. The +3.0 genre bonus isn't enough to overcome the fact that metal is loud (0.98 energy vs 0.10 target → only +0.24) and non-acoustic (+0.01), so it loses ~3.75 points on the other three signals. Meanwhile chill/acoustic songs quietly accumulate ~4.5 points each without ever matching the genre.

This surfaces two real limitations of the additive scoring model:

1. **No signal can veto another.** A profile that is internally contradictory ("I love metal but only want quiet acoustic songs") produces a blended, somewhat incoherent list rather than flagging the contradiction. A production system might weight the explicit favorite genre more heavily, or detect that the request is unsatisfiable.
2. **The reason strings can read as nonsense.** `Iron Verdict` reports *"Acousticness 0.01 (you like acoustic) (+0.01)"* — technically correct, but it awards (a tiny amount of) credit for "liking acoustic" to one of the least-acoustic songs in the catalog. The explanation logic doesn't distinguish "matched your preference" from "barely earned points despite contradicting it."

---

## Experiments You Tried

Below are the experiments I ran while building and tuning the recommender.

- **Closeness vs. magnitude for energy.** I confirmed the scorer rewards being *close* to the target energy, not simply having high energy. With a target of 0.80, "Basement Groove" (energy 0.80) earned the full +2.00 even though it isn't a pop song, while "Gym Hero" (energy 0.93) only earned +1.74 despite being *more* energetic. This is the intended behavior.
- **Case sensitivity in matching.** An early profile used capitalized values like `"EDM"` and `"Intense"`, but the CSV stores genres/moods in lowercase. A plain `==` check matched *nothing*, silently zeroing out genre and mood points. I fixed this by lowercasing both sides (`.lower()`) inside `score_song()`.
- **Mood-label mismatch.** With only one EDM song (labeled `energetic`), an "intense EDM" listener earned genre points but *no* mood points on their favorite genre — and "intense rock" nearly tied the EDM pick. Adding intense EDM tracks ("Detonate", "Wreckage") gave the profile real matches and fixed the ranking.
- **Growing the catalog (10 → 24 songs).** I added new genres (hip-hop, edm, r&b, metal, country, classical, reggae, funk, drum & bass, folk) and moods, plus a cluster of 5 EDM songs spanning intense → melodic. This let me test *intra-genre* ranking (does it order EDM songs correctly?) rather than only across-genre ranking.
- **Different user profiles.** Swapping the profile from `genre=pop, mood=happy` to `genre=edm, mood=intense` produced clearly different top-5 lists, confirming the recommendations are actually driven by the profile.

---

## Limitations and Risks

Limitations I identified in the current recommender:

- **Tiny catalog.** Only 24 songs, so results are not representative of a real music library.
- **Hand-authored feature values.** The energy, tempo, and acousticness numbers were written by hand (including songs styled after real artists), not measured from actual audio — so they're subjective and could be wrong.
- **Exact-match categorical scoring is brittle.** Genre and mood only score on an *exact* match. "indie pop" earns 0 against "pop", and "energetic" earns 0 against "intense", even though they're closely related. There's no partial credit for similar categories.
- **Unused data.** The catalog stores `tempo_bpm`, `valence`, and `danceability`, but the implemented scorer only uses genre, mood, energy, and acousticness. Artist similarity and popularity aren't scored at all yet.
- **No understanding of lyrics, language, or culture.** The system only sees numbers and short text labels.
- **Filter-bubble risk.** Because it rewards similarity to what the user already likes, it tends to recommend "more of the same" and rarely surprises the listener with genuine discovery.
- **Cold-start problem.** A brand-new user with no stated preferences, or a new song with missing/incorrect metadata, is hard to handle well.
- **Weights encode value judgments.** The point weights (genre +3, mood +2, energy +2, acoustic +1) are choices I made. Weighting genre highest, for example, assumes genre matters most — which may not be true for every listener.

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this



