# Grid Fragility Analysis — Methodology Decisions

Decisions made during development, the reasoning behind each, and alternatives considered.

---

## 1. Stress Index Formula

**Decision:** `stress_z = z_daily_peak_mw + z_daily_max_ramp_mw` — two components, no duration term.

**Why:** A duration component (pct_hours_near_peak and four other candidates) was systematically tested. Every candidate failed one of two criteria:
- Relative-to-peak duration metrics (e.g., hours above daily P90): *negatively* correlated with stress_z — adding them would reduce the score on extreme days, which is wrong
- Annual-percentile metrics (e.g., hours above annual P75): positively correlated but r > 0.80 with z_peak — nearly redundant, just adding weight to the same signal

Duration measures how long load stays elevated *relative to that day's own distribution*, which doesn't scale with severity. A low-peak day with sustained duration scores similarly to a high-peak day with moderate duration. See `scratch_duration_justification.py` and `reports/figures/validation/duration_metric_justification.csv`.

---

## 2. K-Means Feature Matrix

### Original matrix (rejected)
`[daily_peak_mw, daily_min_mw, daily_range_mw, daily_max_ramp_mw, daily_ramp_std, z_daily_peak_mw, z_daily_max_ramp_mw, stress_z]`

**Problem:** `stress_z = z_daily_peak_mw + z_daily_max_ramp_mw`, so those three columns are nearly identical linear combinations of each other. Clusters were being defined partly by stress level, then characterized by stress level — circular. The algorithm was recovering an input rather than discovering structure.

### Interim redesign (implemented, then superseded)
`[daily_peak_mw, daily_min_mw, daily_max_ramp_mw, daily_ramp_std, daily_energy_mwh]` with within-BA StandardScaler → PCA (3 components) → K-means.

**Why superseded:** Removed the circularity, but introduced a different distortion. Three features measure load level (peak, min, energy: r = 0.75–0.95 pairwise), two measure ramp (max_ramp, ramp_std: r = 0.77–0.87). PCA compresses these to orthogonal axes, but PC1 (load direction) ends up with ~6x more absolute variance than PC2 (ramp direction) because three collinear features voted together to inflate it. K-means on raw PC scores treated PC1 as 6x more influential than PC2 — the load dimension was over-weighted not because it matters more, but because it had more columns.

### Final decision
`[z_daily_peak_mw, z_daily_max_ramp_mw]` only. No StandardScaler (already within-BA normalized). No PCA (2 features don't require it). K-means directly in 2D z-score space.

**Why this is correct:**
- Both dimensions are already within-BA z-scored (mean = 0, std = 1) — K-means weights them equally
- r = 0.65 between them — genuinely independent, minimal redundancy
- Directly represents the two causal stress mechanisms (capacity stress, response-rate stress)
- Cluster geometry is fully interpretable as a z_peak vs z_ramp scatter plot with no projection needed
- Stress_z (the outcome) emerges as a discovered property of each cluster rather than shaping the clusters

---

## 3. Features Considered and Rejected for Clustering

### daily_energy_mwh (r = 0.92–0.95 with peak)
Nearly entirely redundant with z_peak. More importantly, high sustained energy is *not* independently a grid stress signal — the grid adapts to sustained demand through day-ahead scheduling. It is peaks (generation capacity limits) and ramps (response rate limits) that cause failures. A grid running at 80% of capacity for 24 hours is operationally routine; the same grid hitting 98% for 2 hours with a 3 GW/hour ramp-up is an emergency.

Energy is relevant to *design* (fuel contracts, transmission thermal ratings, storage sizing) but not to operational stress clustering. It is included as a data column for design-oriented outputs.

### daily_min_mw (r = 0.75–0.90 with peak)
Captures the overnight load floor — whether the system got to recover between events. Genuine signal (high min = elevated baseline the next morning), but too correlated with peak to add an independent clustering dimension. Included as a characterization output column, not a clustering input.

### daily_ramp_std (r = 0.77–0.87 with max_ramp)
Captures ramp variability (sustained choppy ramp vs. single spike). Redundant with daily_max_ramp_mw for clustering purposes.

### Day-over-day ramp (daily_peak_mw.diff() per BA)
Would capture rapid-onset events — cold snaps build in 1–3 days versus heat waves at 6–7 days. Rejected because it introduces temporal dependency into a cross-sectional analysis: the same operating conditions on an isolated day would cluster differently than mid-episode, which isn't meaningful. This signal is already captured in Module 7 event onset analysis, where it belongs.

---

## 4. Normalization

K-means uses Euclidean distance. Features with larger absolute variance dominate. CISO peaks at ~25–40 GW; PJM peaks at ~90–160 GW. Without normalization, cluster membership would partly reflect grid size rather than operating regime.

Within-BA normalization is correct because we are asking "how unusual is this day for *this system*" — not comparing absolute MW values across systems. The pre-computed z-scores (z_daily_peak_mw, z_daily_max_ramp_mw) are already within-BA z-scored, so no additional StandardScaler is needed when using them as features.

Global standardization (across both BAs) would compress CISO and PJM into partially overlapping regions based on absolute load values and partially mix their regime signals.

---

## 5. Why PCA Cannot Fix Redundant Features

PCA is a rotation. It correctly finds orthogonal axes and de-duplicates correlated features into a single principal component. But it preserves total variance — the eigenvalues (PC variances) reflect the input covariance structure.

When redundant features share variance, that variance pools into PC1, giving it a larger absolute variance than PC2. K-means on raw PC scores treats all dimensions symmetrically by squaring coordinate differences. A feature with higher variance produces larger squared differences between points and dominates cluster assignments regardless of its label.

Concretely: if PC1 has variance 4.1 and PC2 has variance 0.65, a typical point-to-point separation along PC1 contributes (2.0)² = 4.0 to squared distance while the same relative separation along PC2 contributes (0.8)² = 0.64. The load dimension gets ~6x more influence. PCA found the right directions; K-means then ignored the weaker one.

The fix is not to pass redundant features through PCA — it is to enter only independent, equally-weighted features from the start.

---

## 6. Cluster Separation: Per-BA

K-means is run independently per BA. This is correct because:
1. The two BAs have very different absolute load scales
2. "Extreme stress" means different things for a ~30 GW system vs. a ~130 GW system
3. The stress regimes are operationally specific to each BA (CISO: duck curve / ramp; PJM: heat dome / cold snap)

Clustering both BAs together in a shared feature space would risk finding clusters that partially separate by grid identity rather than operating regime.

---

## 7. Cluster Regime Structure

Four clusters per BA (k = 4). Structure discovered from data, then labeled by inspecting seasonal composition and z-score characterization.

**CISO:**
| Label | Character |
|---|---|
| Stable | Low z_peak and z_ramp; mostly shoulder and winter days |
| Moderate | Near-average both dimensions; mixed seasons |
| Elevated | Moderately elevated both; ~97% summer |
| Extreme Summer | High z_peak AND high z_ramp simultaneously; 100% summer. CAISO requires both — the duck curve generates catastrophic ramp stress only when peak load is already elevated. |

**PJM:**
| Label | Character |
|---|---|
| Stable | Low z_peak and z_ramp; mostly shoulder |
| Moderate | Near-average; mixed seasons |
| Elevated Winter | Elevated z_peak, near-average z_ramp; ~91% winter. High overnight floor from heating loads — different mechanism from summer. |
| Extreme Summer | High z_peak AND high z_ramp; 100% summer. Peak-load dominated. |

The Elevated Winter cluster for PJM (not present in CISO) reflects the cold snap mechanism: polar vortex intrusions push heating demand to multi-day sustained highs without the same rapid ramp signature as summer events.

---

## 8. Operations vs. Design — What This Analysis Covers

**Operations perspective (current analysis):** Given a fixed grid, when does it get stressed, by what mechanism, and how fast does it recover?

**Design perspective (extension planned):** What capacity should be built, and of what type?

The two causal stress mechanisms map directly to design specifications:
- z_peak → total installed generation capacity (must cover peak with reserve margin)
- z_ramp → fast-response resources required (storage, peaker plants, demand response). Ramp magnitude, not peak, determines this — you cannot solve a duck curve problem by adding more solar or baseload.

Energy (MWh/day) is relevant to design for fuel contracts, capacity factors, and transmission thermal ratings, but is not a direct stress signal and is not used in clustering.

### Planned: Load Duration Curve Analysis

A load duration curve — demand sorted from highest to lowest across all hours in the year — is the standard tool for generation planning. It shows:
- Total installed capacity needed (the peak of the curve)
- Hours per year each generation tier must operate (drives capacity factor economics)
- The shape of the generation mix required (baseload vs. mid-merit vs. peaker)

**Planned addition:** Stratified load duration curves per BA per cluster regime. A designer reading the Extreme Summer regime curve can directly derive the capacity and ramp storage requirements for that regime, and how many hours per year the system spends there.

This is a Module 5 storytelling addition. All required data already exists.
