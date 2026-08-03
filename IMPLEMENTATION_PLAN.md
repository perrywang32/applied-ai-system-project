# Implementation Plan — Reliability & Testing System

**Advanced AI feature:** Reliability / Testing System layered on top of the existing
music recommender.

## Guiding constraints

- The existing recommender is the **foundation** and must not be redesigned or replaced.
  Specifically, the scoring math in `score_song()` and the ranking in `recommend_songs()`
  in [src/recommender.py](src/recommender.py) stay behaviorally identical.
- The reliability features are added as **new modules** and **thin integration points**,
  so the recommender can still be imported and used exactly as it is today.
- Each step is small, independently testable, and leaves the app runnable
  (`python -m src.main`) and the test suite green (`pytest`) before the next step begins.

## Foundation facts this plan builds on

- The working pipeline is dict-based and functional: `load_songs()` → `score_song()` →
  `recommend_songs()`, used by [src/main.py](src/main.py) and [run_profiles.py](run_profiles.py).
- `score_song()` returns `(score, reasons)`. The maximum achievable score is
  **8.0** (genre +3.0, mood +2.0, energy +2.0, acoustic +1.0). This ceiling is the
  anchor for confidence normalization.
- Dataset schema (`data/songs.csv`): `id, title, artist, genre, mood, energy,
  tempo_bpm, valence, danceability, acousticness`. Numeric feature range is `[0, 1]`
  except `tempo_bpm`.
- The OOP `Recommender` class is a placeholder; expanded tests will focus on the
  functional pipeline plus the new reliability modules.

---

## Step 1 — Input validation

**Files**
- Create `src/validation.py` (new module: `validate_user_prefs(prefs) -> ValidationResult`).
- Modify `src/main.py` to call it before `recommend_songs()`.

**Why**
The pipeline currently trusts whatever dict it is handed. A missing key, a string where
a float is expected, or an out-of-range `target_energy` produces silent wrong scores or a
crash deep inside `score_song()`. Validating at the boundary is the first reliability gate.

**What it does / expected behavior**
- Accepts the same `user_prefs` dict shape used today (`genre`/`favorite_genre`,
  `mood`/`favorite_mood`, `target_energy`/`energy`, `likes_acoustic`).
- Checks: types are correct; `target_energy` ∈ `[0, 1]`; `likes_acoustic` is boolean or
  absent; genre/mood are non-empty strings when present.
- Returns a structured result: `ok` flag, list of errors, and a **normalized** copy of the
  prefs (e.g. trimmed/lowercased genre) — normalization only, no scoring change.
- On invalid input, `main.py` prints a clear message and exits gracefully instead of
  producing a garbage ranking.

**How to test**
Add `tests/test_validation.py`: valid prefs pass; `target_energy=1.5` fails; `target_energy="high"`
fails; empty genre fails; a fully valid dict returns a normalized copy unchanged in meaning.

---

## Step 2 — Dataset validation

**Files**
- Modify `src/validation.py` (add `validate_dataset(songs) -> ValidationResult`).
- Modify `load_songs()` in [src/recommender.py](src/recommender.py) to optionally run the
  check (behind a parameter defaulting to off, so existing callers are unaffected), or call
  it from `main.py` right after loading.

**Why**
Every recommendation depends on the catalog. A malformed CSV row (missing column, energy of
`2.0`, blank genre, duplicate id) corrupts scoring for *all* users. Validating the dataset
once at load time catches data problems before they become recommendation problems.

**What it does / expected behavior**
- Confirms required columns exist and every row parses.
- Confirms numeric feature values are in `[0, 1]` (except `tempo_bpm`), ids are unique,
  and categorical fields are non-empty.
- Returns a report listing any bad rows; the app can warn-and-continue or refuse to run,
  configurable but defaulting to **warn** so a single bad row doesn't kill the demo.

**How to test**
Add `tests/test_dataset_validation.py` using small in-memory song lists and a temporary CSV in
the scratch/test tmp dir: a clean catalog passes; energy `1.4` is flagged; a duplicate id is
flagged; a missing column is flagged.

---

## Step 3 — Confidence scoring

**Files**
- Create `src/confidence.py` (`score_confidence(ranked, prefs) -> ConfidenceReport`).
- Modify `src/main.py` / `print_recommendations` to display the confidence value.

**Why**
The recommender always returns a top-K list, even when nothing really matches. Confidence
turns "here are 5 songs" into "here are 5 songs, and here is how much you should trust them,"
which is the core reliability signal for the fallback step.

**What it does / expected behavior**
Computes a normalized confidence in `[0, 1]` from signals already available in the ranked
output — **no change to `score_song()`**:
- **Top-score ratio:** `top_score / 8.0` (the known max).
- **Margin:** gap between rank #1 and rank #2 (a clear leader is more trustworthy than a tie).
- **Signal coverage:** how many of the user's stated preferences actually matched on the top pick
  (derivable from the `reasons` list `score_song` already returns).
- Emits a label (`high` / `medium` / `low`) using documented thresholds, plus the raw number
  and the factors behind it.

**How to test**
Add `tests/test_confidence.py`: the all-signals-agree EDM profile yields high confidence; the
adversarial metal/chill/0.1 profile yields low confidence; confidence is always within `[0, 1]`;
a wider #1–#2 margin never lowers confidence.

---

## Step 4 — Conflict detection

**Files**
- Create `src/conflicts.py` (`detect_conflicts(prefs, songs) -> list[Conflict]`).
- Modify `src/main.py` to surface detected conflicts.

**Why**
Some profiles are internally contradictory — the README's metal + chill + 0.1-energy + acoustic
case is the canonical example, where no song can satisfy all signals at once. Detecting this
*before* ranking explains *why* confidence is low and sets up an honest fallback.

**What it does / expected behavior**
- **Weak preference:** flags when the favorite genre/mood has zero or one supporting song in the
  catalog (data-driven, using the loaded songs), so the user is warned the top-5 will be filler.
- **Contradiction:** flags when stated preferences pull in opposite directions — e.g. the favorite
  genre's typical energy/acousticness (averaged from that genre's songs) is far from the requested
  `target_energy` / `likes_acoustic`. Purely diagnostic; it does not alter scores.
- Returns a list of typed conflicts with human-readable messages.

**How to test**
Add `tests/test_conflicts.py`: the adversarial profile reports a contradiction; a `folk` favorite
(single song in catalog) reports a weak/underrepresented-genre conflict; the coherent EDM profile
reports no conflicts.

---

## Step 5 — Fallback behavior for low-confidence recommendations

**Files**
- Create `src/fallback.py` (`apply_fallback(ranked, confidence, prefs, songs) -> FallbackResult`).
- Modify `src/main.py` to route through it and label fallback output.

**Why**
When confidence is low or conflicts exist, silently presenting a shaky top-5 as if it were
trustworthy is the failure mode this whole feature exists to prevent. Fallback makes the system
degrade honestly.

**What it does / expected behavior**
- If confidence ≥ threshold: pass the normal ranking through unchanged.
- If confidence < threshold: return the same songs but clearly **flagged as low-confidence**, add
  a plain-language explanation (drawn from the conflict report), and optionally provide a
  **diversified** fallback list (e.g. broaden beyond the exact-match genre, or fall back to
  strong all-round matches) so the user still gets something reasonable.
- Never fabricates songs and never silently drops the reliability signal — the caller always
  knows whether it received a confident or a fallback result.

**How to test**
Add `tests/test_fallback.py`: high-confidence input passes through untouched; low-confidence input
is flagged and carries an explanation; fallback output is still a valid, correctly typed
recommendation list.

---

## Step 6 — Logging and error handling

**Files**
- Create `src/logging_config.py` (central logger setup).
- Modify `src/recommender.py`, `src/validation.py`, `src/confidence.py`, `src/conflicts.py`,
  `src/fallback.py`, and `src/main.py` to log through it and wrap the top-level `main()` in
  structured error handling.

**Why**
Reliability requires observability. Replacing the lone `print()` in `load_songs()` with real
logging, and catching/reporting errors at the boundary, means failures become diagnosable
instead of raw tracebacks — and validation/confidence/fallback events leave an audit trail.

**What it does / expected behavior**
- One configured logger (level via env var, default INFO) writing readable, timestamped lines.
- Key events logged: songs loaded, validation failures, computed confidence, conflicts detected,
  fallback triggered.
- `main()` wraps execution so an unexpected exception is logged with context and exits non-zero
  with a clear message rather than dumping a traceback. Existing user-facing console output is
  preserved (logging is additive, not a replacement for the pretty recommendation printout).

**How to test**
Add `tests/test_logging.py` using pytest's `caplog`: loading songs emits an info log; invalid
prefs emit a warning/error log; a forced exception in `main()` is caught and logged rather than
propagated.

---

## Step 7 — Automated evaluation metrics

**Files**
- Create `src/evaluation.py` (metrics over a set of profiles).
- Create `experiments/eval_profiles.py` (a runnable harness) or extend
  [run_profiles.py](run_profiles.py).
- Write results to `experiments/evaluation_results.md`.

**Why**
The project currently evaluates by eyeballing printed output. Automated metrics make reliability
claims measurable and repeatable, and give the model card real numbers instead of anecdotes.

**What it does / expected behavior**
Computes, over a fixed set of test profiles, metrics such as:
- **Top-1 genre-match rate** (did #1 match the requested genre?).
- **Average confidence** per profile and overall.
- **Conflict/low-confidence rate** across profiles.
- **Score separation** (mean #1–#2 margin).

Prints a summary table and saves it to `experiments/evaluation_results.md`. Deterministic — same
catalog and profiles produce the same numbers.

**How to test**
Add `tests/test_evaluation.py`: metrics run end-to-end on the real catalog without error; each
metric falls in its valid range; a known-good profile produces the expected genre-match result.

---

## Step 8 — Wire the OOP `Recommender` class to the functional logic

**Files**
- Modify [src/recommender.py](src/recommender.py) (`Recommender.recommend`,
  `Recommender.explain_recommendation`).

**Why**
The starter [tests/test_recommender.py](tests/test_recommender.py) targets the OOP class, but
`recommend()` is a placeholder (`return self.songs[:k]`) that only passes by luck. Making the class
**delegate to the already-working functional logic** means the tests exercise real ranking instead
of an accident, without introducing a second, divergent scoring implementation.

**What it does / expected behavior**
- `Recommender.recommend(user, k)` converts the `UserProfile` dataclass into the `user_prefs` dict
  the functional API expects, calls `recommend_songs()`, and returns the ranked `Song` objects
  (or their dict form) sorted by score — **reusing** `score_song`/`recommend_songs`, not
  reimplementing them.
- `Recommender.explain_recommendation(user, song)` returns the human-readable `reasons` that
  `score_song()` already produces for that song and profile.
- The scoring math itself is unchanged; this step only bridges the OOP surface to the functional
  core so both APIs give identical results.

**How to test**
Update/extend [tests/test_recommender.py](tests/test_recommender.py): `recommend()` on the small
two-song fixture returns songs ordered by real score (pop/happy/high-energy first);
`explain_recommendation()` returns the actual reason strings, not a placeholder; the OOP result
matches the functional `recommend_songs()` result for the same profile.

---

## Step 9 — Expanded pytest tests

**Files**
- Modify [tests/test_recommender.py](tests/test_recommender.py).
- Ensure `tests/test_validation.py`, `tests/test_dataset_validation.py`, `tests/test_confidence.py`,
  `tests/test_conflicts.py`, `tests/test_fallback.py`, `tests/test_logging.py`,
  `tests/test_evaluation.py` from earlier steps are cohesive.

**Why**
The starter suite only exercises the placeholder OOP class. A reliability system needs tests that
cover the *functional pipeline*, the *OOP surface wired up in Step 8*, and the *edge cases* the
reliability layer is meant to handle, including the adversarial profile.

**What it does / expected behavior**
- Adds direct tests for `score_song()` (each signal's point contribution, case-insensitivity,
  energy-closeness) and `recommend_songs()` (ranking order, `k` cap, empty catalog).
- Adds an integration test running validation → recommend → confidence → conflict → fallback on
  the real 24-song catalog for a coherent profile and the adversarial profile.
- All tests pass with plain `pytest`; no network or external state.

**How to test**
Run `pytest -q`; confirm all new and existing tests pass and that coverage now includes the
functional pipeline and every reliability module.

---

## Step 10 — Mermaid architecture diagram

**Files**
- Create `docs/architecture.md` (Mermaid source) and/or embed the diagram in `README.md`.

**Why**
The system now has several cooperating modules (validation, confidence, conflict, fallback,
logging, evaluation). A diagram makes the reliability data-flow legible to a grader at a glance.

**What it does / expected behavior**
A Mermaid `flowchart` showing: input → **input validation** → `load_songs` + **dataset validation**
→ `score_song`/`recommend_songs` → **confidence scoring** → **conflict detection** →
**fallback** → output, with **logging** as a cross-cutting node. Renders on GitHub without extra
tooling.

**How to test**
Preview the Markdown on GitHub (or a Mermaid live editor) to confirm it renders; verify every box
maps to a real module/function delivered in Steps 1–7.

---

## Step 11 — README updates

**Files**
- Modify [README.md](README.md).

**Why**
The README documents only the base recommender. It must explain the advanced reliability feature,
how to run the evaluation harness, and how to interpret confidence/fallback output.

**What it does / expected behavior**
- New "Reliability & Testing System" section describing each feature (Steps 1–7) in plain language.
- Updated "Running Tests" and a new "Running Evaluation" subsection.
- Embedded or linked architecture diagram (Step 9).
- Sample output updated to show a confidence value and a low-confidence/fallback example (the
  adversarial profile is the natural showcase). Existing base-recommender content is preserved.

**How to test**
Re-read the README top to bottom; run every command it lists (`python -m src.main`, `pytest`, the
eval harness) and confirm the documented behavior matches actual output.

---

## Step 12 — model_card.md

**Files**
- Modify [model_card.md](model_card.md).

**Why**
The model card must reflect the system as it now exists — with reliability safeguards — not just
the base scorer. This is where the advanced feature is justified and its limits are stated.

**What it does / expected behavior**
- Updates **How the Model Works** to include validation, confidence, conflict detection, and
  fallback.
- Adds the **automated evaluation metrics** (real numbers from Step 7) to the Evaluation section.
- Updates **Limitations/Bias** to note what reliability catches (contradictory profiles, weak
  genres) and what it still cannot fix (the exact-match scoring cliff, tiny catalog).
- Keeps the existing reflective content; extends rather than rewrites.

**How to test**
Cross-check every claim against the shipped code and the evaluation results file; confirm no
number is invented and every described behavior is demonstrable via the test suite or the app.

---

## Suggested commit cadence

One commit per step, each leaving `pytest` green and `python -m src.main` runnable:
`validation → dataset validation → confidence → conflicts → fallback → logging → evaluation →
wire OOP class → expanded tests → diagram → README → model card`.
