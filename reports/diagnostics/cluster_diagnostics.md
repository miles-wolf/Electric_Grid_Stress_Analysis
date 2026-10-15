# Cluster Diagnostics Report

_Auto-derived from `daily_with_clusters.csv` (730 rows, 2 BA(s))._

## CISO

- Silhouette score: **0.398** (higher = tighter clusters; range -1 to 1)

| cluster | label | n_days | mean_stress_z | max_stress_z | season_mix |
|---|---|---|---|---|---|
| 0 | Stable | 160 | -1.48 | -0.22 | Shoulder 68%, Winter 27%, Summer 6% |
| 2 | Moderate | 108 | 0.10 | 2.05 | Winter 44%, Shoulder 37%, Summer 19% |
| 1 | Elevated | 65 | 1.42 | 3.06 | Summer 92%, Shoulder 8% |
| 3 | Extreme | 32 | 4.13 | 6.60 | Summer 100% |

**Extreme clusters by season:** Summer → cluster 3 (Extreme)

## PJM

- Silhouette score: **0.407** (higher = tighter clusters; range -1 to 1)

| cluster | label | n_days | mean_stress_z | max_stress_z | season_mix |
|---|---|---|---|---|---|
| 0 | Stable | 89 | -2.18 | -0.96 | Shoulder 69%, Winter 20%, Summer 11% |
| 2 | Moderate | 110 | -0.20 | 1.59 | Shoulder 76%, Winter 13%, Summer 11% |
| 3 | Elevated | 96 | 0.28 | 1.42 | Winter 46%, Summer 46%, Shoulder 8% |
| 1 | Extreme | 70 | 2.71 | 4.83 | Summer 80%, Winter 20% |

**Extreme clusters by season:** Summer → cluster 1 (Extreme)
