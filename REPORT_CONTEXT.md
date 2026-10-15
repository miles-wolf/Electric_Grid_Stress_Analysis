# Electric Grid Demand Stress Analysis — Report Context

This document summarises the full analysis for use when writing the report in a new project.
Paste it in at the start of a new session.

---

## Report Title

**Electric Grid Demand Stress Analysis**
Subtitle: *Episodic Demand Stress in U.S. Balancing Authorities — PJM and CAISO, 2025*

---

## What This Analysis Is (and Isn't)

This is a **demand-side analysis only**. It measures how unusual daily load and ramp conditions were, not whether the grid actually struggled to meet them. No supply, capacity, outage, or frequency data is included. The framing should be:

> "On which days were demand conditions most anomalous, and what do those days have in common?"

Not: "On which days was the grid at risk of failure." Using "fragility" was considered and rejected as overreaching — that would require reserve margin and reliability data.

---

## Data Source

- **EIA-930 Consolidated Balance**, 2025 full calendar year
- Two balancing authorities: **PJM Interconnection** and **CAISO** (labelled `CISO` in raw data, displayed as `CAISO`)
- Hourly demand readings, adjusted column: `demand_(mw)_(adjusted)`
- 17,520 hourly rows total (8,760 per BA)
- One spike repair applied: CAISO 2025-07-31 21:00 UTC (11,819 MW reading interpolated — confirmed data error, not a real event)
- Jan 1, 2026 spillover rows excluded from all analysis

---

## Demand Stress Index

### Formula

```
stress_z = z_daily_peak_mw + z_daily_max_ramp_mw
```

Both components are z-scored **within each BA** (per-BA mean and std, ddof=0). The index is unitless and mean-zero by construction.

A 0–1 rescaled version (`stress_01`) is also computed per BA for visualisation.

### Why two components

A duration term (time spent near peak) was evaluated and rejected. Five candidates were tested:

| Metric | r with z_peak | r with stress_z | Verdict |
|--------|--------------|-----------------|---------|
| % hours ≥ 95% of daily peak | −0.19 | −0.16 | Wrong direction |
| % hours ≥ 85% of daily peak | −0.42 | −0.40 | Wrong direction |
| % hours above annual P90 | +0.85 | +0.78 | Redundant with peak |
| % hours above annual P75 | +0.90 | +0.79 | Redundant with peak |
| Smooth multiplier (z* = z_pct × max(0, z_peak)) | −0.43 | −0.42 | Wrong direction |

Relative-to-daily-peak metrics are **negatively** correlated with stress because extreme days have spiky load profiles (few hours near the daily peak), while ordinary days have flat profiles (many hours near the daily max even though it's low). Annual-percentile metrics are **positively** correlated but near-perfectly redundant with z_daily_peak_mw (r > 0.85), adding no independent information.

Full correlation table: `reports/figures/validation/duration_metric_justification.csv`

### Note on component correlations

Since stress_z is the exact sum of two equal-variance z-scores, each component has an identical Pearson r with stress_z by construction. A correlation chart comparing component-to-index correlations will always show equal bars for a two-component equal-weight index — this is a mathematical identity, not a finding.

---

## Key Findings

### 1. Stress is episodic
The vast majority of days are ordinary. Extreme stress concentrates in a small number of events. CAISO has 36 extreme days (~10% of the year); PJM has 64 (~17%). This is confirmed by K-means clustering: one tight extreme cluster, two or three large stable/moderate clusters per BA.

### 2. CAISO: conjoint peak-and-ramp stress, summer-concentrated
- All top stress days fall in **June–September**
- On high-stress days: peak load contributes 53%, max ramp 47% — both are required simultaneously
- Physical mechanism: sustained heat builds demand over ~6 days; the solar duck curve then creates catastrophic evening ramp stress once load is already elevated. Load is the foundation; ramp is the trigger.
- Top stress day: **2025-09-03** (stress_z = 6.59, peak = 42,408 MW, max ramp = 4,682 MW/hr)

### 3. PJM: load-scale stress, summer heat domes
- All top stress days fall in **June–August**
- On high-stress days: peak load contributes 57%, max ramp 43% — more peak-dominated than CAISO
- Physical mechanism: summer heat domes drive demand to exceptional absolute levels. PJM operates at ~3–4× the scale of CAISO (peak days ~140,000–160,000 MW vs. ~40,000 MW)
- Top stress day: **2025-06-24** (stress_z = 4.83, peak = 158,646 MW, max ramp = 8,521 MW/hr)
- Note: PJM winter cold snaps are elevated but do not cross the extreme threshold (stress_z > 3.0) under the two-component formula

### 4. Stress builds before the peak day
Event composite analysis (±7 days around each extreme event, 4 events per BA):

| BA | Component | Mean onset before peak |
|----|-----------|----------------------|
| CAISO | Peak Load | −5.5 days |
| CAISO | Max Ramp | −4.0 days |
| PJM | Peak Load | −6.5 days |
| PJM | Max Ramp | −4.5 days |

Load stress precedes ramp stress by ~1–2 days in both BAs. For CAISO this matches the heat wave → duck curve sequence. For PJM it reflects gradual heat dome development.

### 5. These patterns are confirmed by three independent analyses
- **Cluster geometry** (K-means + PCA): extreme clusters are tight and BA-mixed, moderate and stable clusters are larger and more diffuse
- **Feature contribution by tier** (Test B): high-stress days show elevated z-scores for both components; the peak/ramp split differs between BAs (53/47 CAISO vs. 57/43 PJM)
- **Temporal event trajectories**: load and ramp z-scores both visibly build in the ±7-day windows around extreme events, with load leading ramp

---

## Top 10 Stress Days

### CAISO
| Rank | Date | stress_z | Peak (MW) | Max Ramp (MW/hr) |
|------|------|----------|-----------|-----------------|
| 1 | 2025-09-03 | 6.59 | 42,408 | 4,682 |
| 2 | 2025-08-07 | 6.19 | 39,804 | 4,815 |
| 3 | 2025-08-21 | 5.45 | 40,881 | 4,180 |
| 4 | 2025-08-30 | 5.29 | 38,175 | 4,481 |
| 5 | 2025-08-31 | 5.23 | 38,953 | 4,326 |

### PJM
| Rank | Date | stress_z | Peak (MW) | Max Ramp (MW/hr) |
|------|------|----------|-----------|-----------------|
| 1 | 2025-06-24 | 4.83 | 158,646 | 8,521 |
| 2 | 2025-07-29 | 4.76 | 154,380 | 8,757 |
| 3 | 2025-06-23 | 4.70 | 160,560 | 8,191 |
| 4 | 2025-08-12 | 4.64 | 146,576 | 9,183 |
| 5 | 2025-06-25 | 4.18 | 154,755 | 7,931 |

Full top-10 tables: `reports/figures/stress_daily/top_days_table.csv`

---

## Cluster Structure

K-means, k=4, random_state=42, n_init=20, fitted separately per BA.

### CAISO
| Cluster | Days | Mean stress_z | Character |
|---------|------|--------------|-----------|
| 1 | 36 | +3.99 | Extreme (late summer heat/duck curve events) |
| 3 | 69 | +1.34 | Elevated (warm days with moderate ramp) |
| 2 | 123 | −0.10 | Mild (shoulder season) |
| 0 | 138 | −1.62 | Stable (winter low-demand) |

### PJM
| Cluster | Days | Mean stress_z | Character |
|---------|------|--------------|-----------|
| 0 | 64 | +2.66 | Extreme (summer heat domes) |
| 2 | 71 | +0.80 | Elevated (warm days at scale) |
| 1 | 148 | −0.27 | Mild (shoulder/moderate) |
| 3 | 83 | −2.25 | Stable (low-demand winter) |

---

## Output Files

| File | Description |
|------|-------------|
| `data/processed/stress/daily_stress_pjm_ciso_2025.parquet` | Main daily fact table (732 rows) |
| `data/processed/stress/daily_stress_pjm_ciso_2025.csv` | Same, CSV format for Power BI |
| `data/processed/unsupervised/daily_with_clusters.csv` | Daily data + cluster + PCA scores |
| `data/processed/unsupervised/ciso/cluster_feature_means.csv` | CAISO cluster feature means |
| `data/processed/unsupervised/pjm/cluster_feature_means.csv` | PJM cluster feature means |
| `data/processed/unsupervised/ciso/cluster_stress_tails.csv` | CAISO stress_z tail risk by cluster |
| `data/processed/unsupervised/pjm/cluster_stress_tails.csv` | PJM stress_z tail risk by cluster |
| `data/processed/event_composite/event_windows.csv` | ±7-day windows around extreme events (120 rows) |
| `data/processed/event_composite/event_composite.csv` | Mean composite trajectories (30 rows) |
| `data/processed/event_composite/event_onset.csv` | Onset timing summary (4 rows) |
| `reports/figures/stress_daily/top_days_table.csv` | Top 10 stress days per BA |
| `reports/figures/validation/duration_metric_justification.csv` | Duration metric correlation table |

---

## Figures Inventory

### Module 3 — Daily Stress
- `reports/figures/stress_daily/stress_timeseries_stacked.png` — stress_01 over time, both BAs
- `reports/figures/stress_daily/stress_timeseries_appendix.png` — three-panel: unfiltered / z-score / 0-1
- `reports/figures/stress_daily/stress_distribution.png` — histogram of stress_z by BA

### Module 4 — Unsupervised (per BA, in ciso/ and pjm/ subfolders)
- `pca_pc1_pc2_by_cluster_k4.png` — PCA scatter coloured by cluster
- `pca_pc1_pc2_by_stress.png` — PCA scatter coloured by stress_z
- `pca_pc1_pc2_extremes_annotated.png` — extreme cluster highlighted with top-10 dates labelled

### Module 5 — Storytelling
- `reports/figures/storytelling/01_regimes_feature_space/` — cluster geometry in feature space
- `reports/figures/storytelling/02_stress_by_cluster/02_stress_by_cluster_combined.png` — box plots of stress_z by cluster
- `reports/figures/storytelling/03_frequency_vs_stress/03_frequency_vs_stress_combined.png` — cluster frequency vs mean stress scatter
- `reports/figures/storytelling/04_temporal_trajectories/` — ±7-day event windows for top 3 events per BA (6 figures)

### Module 6 — Validation
- `reports/figures/validation/test_b_contributions.png` — feature contribution by stress tier
- `reports/figures/validation/test_c_cluster_membership.png` — cluster day counts by BA

---

## Pipeline

```
make pipeline        # modules 1, 3-6 end to end
make event_composite # module 7 (run after pipeline)
make validate        # validation tests + duration justification table
```

Project root: `C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis`

---

## Scope Limitations (for methodology section)

- Demand-side only — no supply, generation mix, reserve margin, or outage data
- Two BAs only — PJM and CAISO; findings should not be generalised to other regions without re-running
- 2025 calendar year only — one year is insufficient to establish long-term trends or confirm climate signals
- Z-scores are within-BA and within-year — stress_z is relative to each BA's own 2025 baseline, so the scores are not directly comparable between BAs in absolute terms
- Spike repair is minimal (one correction) — the methodology is self-calibrating but any other data quality issues in EIA-930 would propagate

## Potential Extensions (future work)

- Add supply-side data (reserve margins, generation by fuel type) for a true fragility index
- NERC disturbance data and FERC frequency event logs for actual reliability outcomes
- Expand to more BAs and multi-year data for seasonal and trend analysis
- Sub-daily resolution analysis (6-hour blocks) to better characterise ramp timing within extreme days
