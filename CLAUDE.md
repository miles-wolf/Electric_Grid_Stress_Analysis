# Grid Fragility Analysis — Project Brief

Paste this file into Claude Desktop at the start of a session for full context.
Claude Code (CLI) reads this file automatically.

---

## What This Project Is

A Python data science project analyzing electrical grid fragility for two U.S. balancing authorities (BAs) — **PJM Interconnection** and **CAISO (California ISO)** — across the full 2025 calendar year. The end goal is a **Power BI dashboard** for grid operators and designers.

The approach treats each BA as a dynamic system and measures daily fragility as a two-component composite z-score:

```
fragility_z = z_daily_peak_mw + z_daily_max_ramp_mw
```

Both components are z-scored within each BA. A duration term was evaluated (five candidate formulations) but rejected — all candidates either (a) were negatively correlated with fragility or (b) were redundant with peak load (r > 0.85). See `scratch_duration_justification.py` for the correlation table used in the final report.

Project location: `C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis`

---

## Pipeline (run from project root)

```
make pipeline        # modules 1-6 end to end
make event_composite # module 7 (run after pipeline)
```

| Module | Script | Output |
|--------|--------|--------|
| 1 Ingest | src/ingest_eia930.py | Hourly parquet, 17,505 rows |
| 2 Features | src/features_eia930.py | Daily features, 730 rows |
| 3 Fragility | src/fragility_daily.py | Daily fragility scores, 730 rows |
| 4 Unsupervised | src/unsupervised.py | Clusters + PCA plots |
| 5 Storytelling | src/storytelling/*.py | Narrative figures |
| 6 Validation | src/analysis_validation.py | Statistical validation figures |
| 7 Event Composite | src/event_composite.py | Event window/composite/onset CSVs |

---

---

## Key Findings

### CISO (California ISO)
- **Ramp-driven fragility** — extreme events are summer heat waves
- Load builds gradually ~7 days before peak (heat wave development)
- The solar evening drop-off (duck curve) then creates catastrophic ramp stress once load is already elevated — this is the trigger, not the foundation
- Requires BOTH high z_peak AND high z_ramp simultaneously
- One corrupted reading repaired: CAISO 7/31/25 (spike filter)

### PJM Interconnection
- **Load-driven fragility** — extreme events are summer heat domes
- Winter events also appear (cold snaps) and behave very differently:
  - Summer: fragility builds over ~6 days (gradual heat wave)
  - Winter: builds in ~1 day (polar vortex intrusion)
- Seasonal separation is essential — do not mix summer/winter in composite analysis

### Event Composite (Module 7)
Independent extreme events (fragility_z > 3.0, >14 days separation, season-split):
- CISO: 5 Summer events, 0 Winter
- PJM: 3 Summer + 2 Winter events

Onset timing summary:
| BA | Season | Component | Mean onset (days before peak) |
|----|--------|-----------|-------------------------------|
| CISO | Summer | Peak Load | -6.6 |
| CISO | Summer | Max Ramp | -4.0 |
| CISO | Summer | Duration | -2.5 (only 2/5 events) |
| PJM | Summer | Peak Load | -6.3 |
| PJM | Summer | Max Ramp | -3.7 |
| PJM | Winter | Peak Load | -1.0 |
| PJM | Winter | Max Ramp | -2.0 |

---

## Cluster Structure (will shift after rebuild)

Clusters use K-means k=4, random_state=42, n_init=20 — reproducible.
Separate models per BA. Feature matrix has known redundancy (fragility_z = sum of three z-scores already included — biases toward fragility-driven separation).

Current cluster labels (will renumber after rebuild):

**CISO:** Extreme (43 days) | Moderate ramp+peak (94 days) | Moderate duration (100 days) | Stable (128 days)
**PJM:** Extreme (75 days) | Moderate duration (77 days) | Stable slight (138 days) | Stable low (75 days)

Planned: sub-tier the extreme cluster after rebuild (CISO k=2, PJM k=3 within extreme).

---

## Power BI Tables

| File | Rows | Notes |
|------|------|-------|
| data/processed/fragility/daily_fragility_pjm_ciso_2025.csv | 730 | Main fact table |
| data/processed/unsupervised/daily_with_clusters.csv | 730 | + cluster + PCA |
| data/processed/unsupervised/cluster_feature_means.csv | 8 | Per BA + cluster |
| data/processed/unsupervised/cluster_fragility_tails.csv | 8 | p90/p95/max per BA + cluster |
| data/processed/event_composite/event_windows.csv | 150 | ±7 day event windows |
| data/processed/event_composite/event_composite.csv | 45 | Composite trajectories |
| data/processed/event_composite/event_onset.csv | 9 | Onset timing summary |
| reports/figures/fragility_daily/top_days_table.csv | 20 | Top 10 days per BA |

---

## Data Notes
- Raw source: EIA-930 consolidated balance data, 2025 full year
- Jan 1, 2026 rows removed from all datasets (raw data spillover)
- Spike repair: single-hour readings >25% of daily load range from 3-hour rolling median are linearly interpolated. Self-calibrating. One CAISO correction on 7/31/25 (would have consumed an entire K-means cluster without repair).
- Season map: Summer = Jun-Sep | Winter = Dec-Feb | Shoulder = Mar-May, Oct-Nov
