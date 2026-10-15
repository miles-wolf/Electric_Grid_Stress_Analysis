# Projects in this repo

One repo, two analyses that share a core. Each project lists exactly which code it runs.

| | **1. Grid Fragility** (2025, done) | **2. Plugging in a Gigawatt** (data centers, in progress) |
|---|---|---|
| Question | Which days stress PJM and CAISO, and why? | How many GW of data centers can each grid absorb, firm vs flexible? What does it emit? |
| Regions / years | PJM, CISO · 2025 | PJM, ERCO, TVA, MISO, CISO · demand 2019–2025, fuel mix 2025 |
| Run | `make pipeline` then `make event_composite` | `make datacenters` |
| Outputs | `data/processed/{stress,unsupervised,event_composite}/`, `reports/`, `tableau/` | `data/processed/datacenters/` (Parquet, also read by the Caidence Analyst agent) |

## Code map

**Shared core** (both projects): `ingest_eia930.py` · `qc_eia930.py` · `features_eia930.py` ·
`stress_daily.py` · `operational_classifier.py` · `analysis_validation.py` · `config.py`

| Module | Grid Fragility | Data centers | Notes |
|---|---|---|---|
| `ingest_eia930.py` | ✅ | ✅ | Hardcoded to PJM+CISO 2025 files; extend to 5 BAs × 2019–2025 |
| `qc_eia930.py` | ✅ | ✅ | |
| `features_eia930.py` | ✅ | ✅ | |
| `stress_daily.py` | ✅ | ✅ | Peak half only; the ramp half doesn't apply to flat load |
| `operational_classifier.py` | ✅ | ✅ | **Frozen** 2025 baseline + centroids, never refit (regime migration, Step B) |
| `analysis_validation.py` | ✅ | ✅ | Alert-day rate → expected extra alert days |
| `unsupervised.py`, `cluster_diagnostics.py`, `analysis_k_selection.py` | ✅ | — | Fits the regimes the data center project reuses frozen |
| `event_composite*.py`, `stress_tiers.py`, `validation_duration.py`, `stress_daily_unfiltered.py` | ✅ | — | |
| `storytelling/`, `viz.py`, `build_dashboard_tables.py`, `build_page3_table.py` | ✅ | — | Power BI / Tableau tables + figures |
| `features.py`, `feature_utils.py`, `model.py`, `db.py` | ✅ | — | |
| `datacenters/` (Module 8) | — | ✅ | New: hosting-capacity sweep, weather years, regime migration, marginal emissions |

Rule: a module used by both projects stays in `src/`; anything only the data center project uses
goes in `src/datacenters/`. Changing a shared module means re-running both projects.

How each step was done (and which steps could become agent tools): `docs/procedure-log.md`.
