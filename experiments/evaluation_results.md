# Evaluation Results

Deterministic metrics from the real recommender pipeline (`python -m experiments.run_evaluation`).

## Per-profile

| Profile | Conf | Label | Genre | Mood | EnergyErr | Acoustic | Attrs | Fallback |
|---|---|---|---|---|---|---|---|---|
| High-energy EDM | 0.81 | High | 1.0 | 0.4 | 0.046 | 1.0 | 0.8 | no |
| Chill lo-fi | 0.82 | High | 0.6 | 0.6 | 0.042 | 1.0 | 0.8 | no |
| Rock / intense | 0.99 | High | 0.2 | 0.8 | 0.034 | 1.0 | 0.75 | no |
| Adversarial / conflicting | 0.29 | Low | 0.2 | 0.6 | 0.356 | 0.8 | 0.45 | yes |

## Aggregate

```
Evaluated 4 profiles against the catalog:
  Genre match rate:            0.50
  Mood match rate:             0.60
  Average energy error:        0.12
  Acoustic match rate:         0.95
  Attributes satisfied:        0.70
  Low-confidence cases:        1/4
  Fallback activation rate:    0.25
```
