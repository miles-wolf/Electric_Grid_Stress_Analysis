# Grid Stress Analysis — Report Briefing

Goal: Please write a report summarizing the Grid Stress Analysis work done inside this directory. I'd like for the report to have a very clean, complete, coherent executive summary on the first 1-2 pages (preferably one if feasible). The rest of the report should mimic the structure of the previous version of the report (see #10 file index below). additional information to guide you in writing this report is below. Everything is already ran and the important info should be summarized below for you but if you need to run scripts inside the directory to understand things better yourself - by all means. please export the complete report with figures to a .pdf file and the text from the report to an .md file. if you have any questions please do ask before you begin the report or pause your work along the way before proceeding.

Context document for the report-writing agent. The project, its methods, its findings, and the framing decisions are summarized below. Treat this file as authoritative; older docs in `docs/` and `CLAUDE.md` may still use "fragility" terminology or pre-redesign cluster details.

---

## 1. Elevator pitch

A reproducible framework for classifying daily grid operating states from public EIA-930 load data, applied to PJM Interconnection and CAISO across 2025. The framework reveals fundamentally different stress *physics* between the two systems, and ships as a Power BI dashboard plus an operator-facing daily stress calculator. The contribution is the framework and the BA comparison, not the descriptive finding that summer is stressful.

---

## 2. What to lead the report with (in order)

1. **The framework / instrument.** Reproducible regime classifier from public data, with zero-maintenance re-runs via auto-labeling, plug-and-play across BAs and years.
2. **CISO vs PJM physics contrast.** Ramp-driven (solar duck-curve compound failure) vs load-driven (heat-dome buildup, cold-snap demand). Comparative framing is relevant to interconnection planning and capacity expansion.
3. **Character matters, not just magnitude.** Within summer, Elevated (peak-dominant) and Extreme (both-maxed) are operationally different states. The categorical regime structure is the contribution; continuous stress metrics already exist in industry.
4. **Recovery variance as a research question.** Same-severity events recover at different rates, suggesting a second axis (weather persistence?) worth investigating.
5. **Tight event clustering in PJM Summer.** Cumulative stress risk; events sometimes overlap before recovery.

## 3. What NOT to lead with

- "We identified 4 stress regimes." Descriptively true but rudimentary; the regime *count* is not the contribution.
- **Lead-lag between Peak Load and Max Ramp components as a forecast horizon.** It is descriptive event anatomy only. Both components are downstream of the upstream temperature trajectory that operators already track via weather forecasts. Framing it as "a 4–6 day forecast horizon" overstates the contribution.
- "Summer is stressful." Confirmatory, not novel.
- The CAISO Flex Alert / EEA validation null result without context — see Section 7.

---

## 4. Methods

### 4.1 Data

- Source: EIA-930 consolidated balance data, full year 2025
- Two balancing authorities: **PJM Interconnection** (Eastern) and **CAISO** (Western)
- Jan 1, 2026 rows filtered out as raw data spillover
- Spike repair: single-hour readings >25% of daily range from a 3-hour rolling median are linearly interpolated. One CAISO correction on 7/31/25.
- Season map: Summer = Jun-Sep | Winter = Dec-Feb | Shoulder = Mar-May, Oct-Nov

### 4.2 Stress index

```
stress_z = z_daily_peak_mw + z_daily_max_ramp_mw
```

Both components are z-scored within each BA across the full 2025 year (population std, ddof=0).

**A duration component was tested and rejected.** Five candidate duration metrics were evaluated; all failed for one of two reasons:
- Relative-to-peak metrics (% hours within 95%/85% of *that day's own* peak) measured load profile *shape*, not severity. Extreme days have spiky profiles where few hours sit near the daily max; ordinary flat-load days score high. Result: negative correlation with stress — inverse of intent.
- Annual-percentile metrics (% hours above BA P90/P75) were correctly positive with stress but had r > 0.80 with z_peak. Adding them double-counted the peak signal.

Honest framing: a physically meaningful duration metric would require an absolute reference tied to operating headroom (hours above day-ahead reserve margin, or above 95% of nameplate capacity). Neither is in EIA-930. The rejection is therefore a documented data-availability constraint, not a methodological surrender. Justification table: `reports/figures/validation/duration_metric_justification.csv`.

A normalized version `stress_01` = within-BA min-max normalized stress_z is used by the dashboard.

### 4.3 K-means clustering

- Feature matrix: `[z_daily_peak_mw, z_daily_max_ramp_mw]` only. No StandardScaler (features already z-scored), no PCA.
- k = 4, KMeans(random_state=42, n_init=20), per-BA models.
- `daily_energy_mwh` was kept as output but excluded from clustering (r = 0.92–0.95 with peak).

**k = 4 justified by multi-metric sweep** (`reports/figures/k_sweep/`):
- CISO: silhouette 0.398, Davies-Bouldin 0.86 at k=4
- PJM: silhouette 0.407, Davies-Bouldin 0.85 at k=4
- k=4 chosen for cross-BA consistency and operational interpretability over chasing winter regime separation at higher k.

**Auto-labeling shipped (2026-05-13):** hardcoded `CLUSTER_LABELS` and `EXTREME_CLUSTERS` dicts that previously required manual update after each re-run are GONE. Labels are derived at runtime from cluster properties (`src/cluster_diagnostics.py`). Re-runs are safe.

### 4.4 Cluster counts (2025)

| BA | Stable | Moderate | Elevated | Extreme |
|---|---|---|---|---|
| CISO | 160 | 108 | 65 | 32 |
| PJM | 89 | 110 | 96 | 70 |

CISO mean stress_z per cluster: Stable −1.48, Moderate 0.10, Elevated 1.42, Extreme 4.13. CISO Extreme is 100% summer.

PJM mean stress_z per cluster: Stable −2.18, Moderate −0.20, Elevated 0.28, Extreme 2.71. PJM Extreme is 80% summer / 20% winter.

PJM Elevated cluster is 46% Winter / 46% Summer — mixed. **Cluster label alone is not sufficient operational characterization for PJM**; season context matters. The dashboard slicer makes this trivially visible.

### 4.5 Two-tier event extraction

The cluster-based extreme-event extraction misses PJM Winter (no winter-dominated cluster exists at k=4 with this feature set). Rather than complicating the clustering, the project runs a **parallel direct-threshold extraction** by (BA × season × tier):

| BA × Season | Extreme tier | Elevated tier |
|---|---|---|
| CISO Shoulder | 0 | 2 |
| CISO Summer | 4 | 6 |
| PJM Summer | 4 | 6 |
| **PJM Winter** | **3** | **5** |

PJM Winter Extreme top events: Jan 23 (z=2.34), Dec 14 (z=2.29), Feb 18 (z=1.91).

This is what powers the page-3 PJM Winter composite event on the dashboard. **Files**: `data/processed/event_composite/event_*_tiers.csv`. The original cluster-based extreme events are in `event_*.csv` (without `_tiers`).

The previously-planned season-stratified clustering (cluster within (BA, season) separately) was **deferred/superseded** by this approach. Only revisit if a downstream use case specifically needs season-conditioned regime labels.

### 4.6 Operator-facing daily stress calculator

Math lives in Power BI DAX; Python produces reference constants:
- `data/processed/operational/baseline_stats_2025.csv` — per-BA mean/std for daily_peak_mw and daily_max_ramp_mw
- `data/processed/operational/cluster_centroids_2025.csv` — per-BA cluster centroids in (z_peak, z_ramp) space with auto labels

Reference Python: `src/operational_classifier.py` (`classify_day(ba, peak_mw, ramp_mw, ...)`). DAX formulas validated against this.

---

## 5. Findings

### 5.1 CISO — acute and ramp-amplified

- Stress concentrates into a **tight Aug–Sep window** (8 days at z > 4).
- 18 high-stress days total (z_01 > 0.7).
- Extreme events are summer heat waves where ~7 days of temperature buildup elevates load, then the **solar evening drop-off (duck curve) triggers a catastrophic ramp spike** that pushes stress over the edge. Requires BOTH high z_peak AND high z_ramp simultaneously.
- CISO solar penetration ≈ 25%.

### 5.2 PJM — broader and load-led

- Stress builds earlier, holds longer. **46 high-stress days** total — more than 2.5× CISO.
- PJM Summer events: load-dominated, slower build-up and drop-off from heat-dome effect. Ramp is modest.
- PJM Winter events: load-dominated cold snaps that build in ~1–2 days. **Ramp signal is weak or negative.**
- PJM solar penetration ≈ 5%.
- **Tight event clustering in PJM Summer:** events sometimes overlap before recovery — cumulative stress risk.

### 5.3 The within-BA stress magnitude itself is a finding

CAISO extreme days hit ~4σ above CAISO's own mean. PJM extreme days hit only ~2σ above PJM's own mean. Since z-scores are within-BA, this is **substantive, not a charting artifact**: CAISO has a tightly distributed operating regime with rare violent excursions; PJM has a wider distribution where even extreme events don't deviate as far in normalized terms.

Reinforces the acute-vs-broad narrative without any additional measurement.

### 5.4 Compound mechanism on CISO extreme days

Multi-day heat buildup → solar drop-off → ramp spike → Extreme. This is a **two-stage failure mode** that the regime framework captures as a single Extreme class, but operators would benefit from seeing it as a sequence. Worth foregrounding in the report.

### 5.5 Lead-lag between Peak Load and Max Ramp (descriptive only)

Onset timing (mean days before peak):
- CISO Summer: Peak Load −5.5, Max Ramp −4.0
- PJM Summer: Peak Load −6.5, Max Ramp −4.5
- PJM Winter: Peak Load −3.5, Max Ramp −2.5 (shorter — cold snaps come on faster)

**Frame this strictly as event anatomy, not as a forecast advantage.** See Section 3.

### 5.6 Recovery variance

CISO recovery: 6–10 days, severity gradient holds. PJM Summer recovery: 3–9 days (faster than CISO). Same-severity events recover at different rates within each BA — suggests a second axis worth investigating (weather persistence, antecedent moisture, system reset speed).

### 5.7 Additive formula limitation (worth naming honestly)

The additive stress formula can produce near-zero scores for high-peak / low-ramp days. In practice such days are rare (r = 0.65 between components), but the formula is not designed to flag isolated capacity-only stress. Mention as a known constraint.

---

## 6. Power BI dashboard (the deliverable)

Three pages, considered SHIPPED:

**Page 1 — Overview**
- Daily Stress_01 line, Avg Stress by Month (stacked z-Peak / z-Ramp + total), 30-day rolling High Stress Day count
- KPI cards per BA: Stress_Z (Max), Stress_01 (Avg), Most Stressed Day, High Stress Day count
- Most Stressful Days table, BA slicer
- High Stress threshold: Z_01 > 0.7

**Page 2 — ML Clustering**
- Z-score scatter, frequency donut, Avg Z-Scores by Cluster bars, Days × Cluster × Season stacked bar
- Silhouette score table (k=2..6, both BAs)
- **Daily Stress Calculator** (live operator widget). Verified: CISO 40000/3000 → Extreme/94%; PJM 100000/7000 → Moderate/62%.

**Page 3 — Event Drilldown**
- Three composite-event panels: CAISO Summer (ramp-amplified, ~4σ peak), PJM Summer (load-dominated, ~2σ), PJM Winter (load-dominated cold snap, ~1σ)
- Lead Days bars by BA × season × component
- Hourly Demand + Hourly Ramp on Extreme Day with BA + Season slicers
- Summary notes panel

**Design notes for report:**
- Page 3 y-axes are intentionally independent. The page is about event *anatomy* (shape, lead-lag), not magnitude. Independent axes avoid flattening PJM panels; the magnitude story is already told on the Page 1 KPI cards. The within-BA z-magnitude difference (Section 5.3) is itself a finding.
- Snapshots: `reports/dashboard/Grid-Stress-Analysis_Dashboard_{1,2,3}.pdf` (both BAs / CISO / PJM)

---

## 7. External validation — sneak peek (CAISO Flex Alerts + PJM Hot/Cold Weather Alerts)

A first-pass validation against operator-issued alerts. Full year 2025, both seasons, both BAs. Folder: `Insights/sneak_peek_validation/`.

### 7.1 PJM — strong precision

| PJM 2025 | Days | With operator alert | % |
|---|---|---|---|
| Stable | 89 | 3 | 3.4% |
| Moderate | 110 | 2 | 1.8% |
| Elevated | 96 | 1 | 1.0% |
| **Extreme** | **70** | **21** | **30.0%** |

**Of PJM's 27 operator alert-days in 2025, 21 (78%) landed in the Extreme regime.** Strong precision. The 78% holds equally for summer (heat-driven) and winter (cold-driven) alert-days — the model classifies the right days as Extreme across both physical regimes, which independently cross-validates the two-tier event extraction approach.

Recall (% of model-flagged high-stress days that had operator alerts) is only 13%. Expected, not a failure: PJM issues alerts on a subset of stressed days based on reserve forecasts, not on every physically-stressed day.

### 7.2 CAISO — the striking null result

**Zero CAISO operator alerts on any of 32 model-flagged Extreme days, including the top-5 stress days (z = 6.60 → 5.24).** CAISO issued zero Flex Alerts and zero EEAs in all of 2025 — only one RMO (Jan fire weather) and one Transmission Emergency (Apr Rio Oso line).

This is a real model limitation, not a model failure. Three non-exclusive interpretations:

1. **CAISO supply margin caught up post-2020/2022.** Storage and capacity additions decoupled load stress from reserve shortfalls.
2. **The model measures demand-side physical stress, not supply adequacy.** stress_z = peak load + max ramp; alerts trigger on reserve shortfall. The two can decouple.
3. **PJM and CAISO have structurally different alert frameworks.** Flex Alerts are conservation calls, not reserve declarations. The bar for triggering is different.

**Honest framing for the report:** the model is a load/ramp diagnostic, not a reserve-margin forecaster. The asymmetry between PJM (30% alert overlap on Extreme) and CAISO (0%) is itself a substantive finding that reinforces the "different physics, different responses" message with concrete external evidence.

### 7.3 Coverage gap (note for future work)

7 of 14 PJM Winter Extreme days fell outside the compiled Cold Weather Alert windows. Almost all sit 1–4 days adjacent to confirmed alert periods — likely covered by PJM Cold Weather *Advisories* (lower-tier precursor), which weren't compiled in the sneak peek. If Advisories were added, PJM Winter coverage likely jumps from 50% to 90%+.

Also missing: Feb 18 (z=1.91) — a separate Feb cold event not yet researched.

### 7.4 Files

- `Insights/sneak_peek_validation/README.md` — full writeup with caveats
- `Insights/sneak_peek_validation/sneak_peek_validation.py` — reproducible script
- `Insights/sneak_peek_validation/alerts_2025.csv` — alert calendar
- `Insights/sneak_peek_validation/contingency_alert_x_cluster.csv` — contingency table
- `Insights/sneak_peek_validation/stress_with_alerts.png` — timeseries overlay

---

## 8. Known limitations to acknowledge in the report

1. **The model is a diagnostic, not a simulator or a forecaster.** It cannot answer counterfactual questions ("what if we added 5 GW of solar?") without a bottom-up load/capacity model.
2. **The model measures demand-side physical stress, not reserve adequacy.** Section 7.2 above. CAISO's reserve margin reality decoupled it from physical stress in 2025.
3. **Additive stress formula** can miss isolated high-peak / low-ramp days (Section 5.7).
4. **Single-year sample.** 2025 only. Cross-validation against 2020–2022 (especially CAISO when alerts were frequent) is a natural next step.
5. **No ground-truth economic anchor yet.** LMP correlation is the strongest next validation; OE-417 incident data is the strongest precision check.
6. **Within-BA z-scores** mean magnitudes are not directly comparable across BAs. The dashboard handles this via independent axes on Page 3; the report should be explicit about it.
7. **Cluster labels are auto-derived from rank** — robust across re-runs but not anchored to absolute physical thresholds (e.g., MW values). Operator interpretation requires per-BA context.

---

## 9. Future work (the operationally valuable extensions)

In rough order of priority:

1. **Weather-driven predictive modeling.** Given a multi-day temperature forecast plus humidity, cloud cover, wind, predict tomorrow's regime classification. This is the natural operational extension — the regime framework provides categorical decision boundaries; weather forecasts have skill out 7+ days; combining gives operators a categorical risk forecast aligned with their existing frameworks. **This is the operationally valuable forecast tool, NOT the load-component lead-lag.**
2. **LMP correlation** for economic validation (PJM Data Miner 2, CAISO OASIS).
3. **Temperature sensitivity slopes.** Regress stress_z on weather features → "+1°C summer max temp = +X stress_z." Lets the report answer "+2°C climate warming → +N extreme days/year." One-page climate-policy deliverable.
4. **Multi-year backtest**, especially CAISO 2020–2022 when alerts were frequent.
5. **Counterfactual / scenario analysis** (data centers, solar, nuclear) — be honest that this is much harder and requires a bottom-up demand/capacity model. Tractable middle ground: residual-inflation scenarios (detrend observed load, re-inflate under hotter temps).
6. **PJM Cold Weather Advisory compilation** to close the validation coverage gap.

---

## 10. File index

| Path | Purpose |
|---|---|
| `Electric Grid Fragility Analysis.pdf` | Previous report edition - review this to mimic style and formatting |
| `data/processed/stress/daily_stress_pjm_ciso_2025.parquet` | Main fact table (730 rows; has `season`, `stress_01`) |
| `data/processed/unsupervised/daily_with_clusters.csv` | + `cluster` int, `cluster_label`, `ramp_dominant` |
| `data/processed/unsupervised/{ciso,pjm}/cluster_feature_means.csv` | Per-cluster profile + season composition |
| `data/processed/event_composite/event_windows.csv` | Extreme-tier −7/+14 windows (cluster-based; no PJM Winter) |
| `data/processed/event_composite/event_composite.csv` | Extreme-tier composite trajectories |
| `data/processed/event_composite/event_{onset,recovery}.csv` | Extreme-tier timing |
| **`data/processed/event_composite/event_*_tiers.csv`** | **Two-tier events (Extreme + Elevated); INCLUDES PJM Winter — powers dashboard page 3** |
| `Writing_Samples` | subdirectory to reference for mimicing my writing style
| `data/processed/operational/baseline_stats_2025.csv` | Dashboard z-score constants |
| `data/processed/operational/cluster_centroids_2025.csv` | Dashboard centroids + labels |
| `reports/figures/k_sweep/k_sweep_metrics.csv` | k-selection justification |
| `reports/figures/validation/duration_metric_justification.csv` | Duration-component rejection table |
| `reports/diagnostics/cluster_diagnostics.md` | Auto-generated cluster summary |
| `reports/dashboard/Grid-Stress-Analysis_Dashboard_{1,2,3}.pdf` | Dashboard snapshots |
| `Insights/sneak_peek_validation/` | External alert validation, full year 2025 |
| `src/operational_classifier.py` | Reference Python for the calculator |
| `src/cluster_diagnostics.py` | Auto-labeling logic |

---

## 11. Voice / tone guidance

- Lead with substance, not summaries.
- Don't oversell. Frame the descriptive findings ("we identified 4 stress regimes") as confirmatory; frame the framework + comparative BA contrast as the novel contribution.
- Be honest about limitations — naming them well makes the work more credible, not less.
- The lead-lag-as-forecast-horizon framing is the single most tempting overclaim. Avoid it.
- The CAISO null result is the second most tempting thing to overclaim or underclaim. It is neither a validation failure nor a strong validation — it is evidence of a structural difference between systems and a real model limitation. Frame it as both.
- Elevator pitch (for abstract/intro): "Reproducible framework for classifying daily grid operating states from public load data, applied to PJM and CAISO 2025; reveals fundamentally different stress physics between the two systems."
- keep your tone as similar to mine as possible. you can find my writing samples inside the writing_samples subdirectory
    - keep in mind that these are for less formal writing pieces and most of them were written years ago. don't dumb yourself down for this to match my style. but just keep it natural/non-AI sounding as possible
