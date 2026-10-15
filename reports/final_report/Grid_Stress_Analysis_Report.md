# Grid Stress Analysis

### An Applied Analysis of Grid Operating Regimes Using Public Operational Data

**By Miles Wolf**

June 2026 | Supersedes *Electric Grid Fragility Analysis* (original January 2026, revised April 2026)

Full documentation and codebase available here — https://github.com/miles-wolf/Grid-Stress-Analysis

---

## 1. Executive Summary

This report presents a reproducible framework for classifying daily grid operating states from public EIA-930 hourly demand data, applied to two balancing authorities (BAs) — PJM Interconnection on the East Coast and CAISO in California — across calendar year 2025. Each day is scored on a two-component stress index (peak load plus maximum hourly ramp, standardized within each BA), classified into one of four operating regimes by K-Means clustering, and rolled into extreme-event analysis at two severity tiers. The results are validated against operator-issued alerts from both system operators. The framework ships as a three-page Power BI dashboard, including a live daily stress calculator that classifies any (peak load, max ramp) pair into a regime in real time.

The contribution is the instrument and the cross-system comparison, not the unsurprising news that summer is stressful. Regime labels are derived automatically from cluster properties, so re-runs require no manual maintenance, and the pipeline runs on any EIA-930 balancing authority without modification.

Key findings:

- **The two systems stress differently.** CAISO stress is acute and ramp-amplified: roughly a week of heat buildup elevates load, then the evening solar drop-off (the duck curve) fires a ramp spike on top of it — a two-stage compound mechanism that requires both components at once. PJM stress is broad and load-led: heat domes build over about a week in summer, cold snaps arrive in one to two days in winter, and the ramp signal is modest or even negative. PJM logged 46 high-stress days in 2025, more than 2.5× CAISO's 18.
- **The magnitudes differ within each system's own norms.** CAISO extreme days reach roughly 4σ above CAISO's own annual mean; PJM extreme days reach only about 2σ above PJM's. Because scores are standardized within-BA, this is a structural property, not a charting artifact: CAISO runs a tightly distributed operating regime with rare, violent excursions, while PJM runs a wider distribution where even the worst days don't deviate as far in normalized terms.
- **Stress character matters, not just magnitude.** Within summer, Elevated days (peak-dominant) and Extreme days (both components maxed) are operationally distinct states. And in PJM, the Elevated regime splits 46% winter / 46% summer — a regime label alone is not sufficient operational characterization without season context.
- **External validation is strong where it should be, and instructively null where it isn't.** 78% of PJM's 27 operator alert-days in 2025 landed in the model's Extreme regime, holding equally for heat-driven and cold-driven alerts. CAISO issued zero Flex Alerts and zero Energy Emergency Alerts in all of 2025, so none of the 32 model-flagged CAISO extreme days carried an operator alert. The model measures demand-side physical stress, not reserve adequacy — and the asymmetry between the two systems is itself evidence that they are structurally different.
- **Same-severity events recover at different rates** (CAISO 6–10 days, PJM summer 3–9), pointing to a second axis — most plausibly weather persistence — worth measuring. PJM summer events also arrive close enough together that some overlap before recovery completes, a cumulative-stress risk the index makes visible.

The framework is a diagnostic, not a forecaster: it characterizes what stress looks like and when it occurs, not whether reserves will cover it. The natural operational extension is weather-driven regime prediction — temperature forecasts carry skill a week out, and the regime labels produced here are clean categorical targets.

---

## 2. Data and Scope

This analysis draws on EIA Form 930 consolidated hourly operational data for CAISO and PJM Interconnection, covering all 365 days of calendar year 2025 at hourly resolution, aggregated to daily features for modeling (730 BA-days total). Rows spilling into January 1, 2026 were dropped as raw-data overflow.

Data quality filtering is applied at the hourly level before any calculation. Single-hour demand readings deviating from their 3-hour rolling median by more than 25% of that day's load range are flagged as reporting artifacts and replaced by linear interpolation from adjacent hours. The filter is self-calibrating — no BA-specific thresholds required. One reading was corrected in CAISO (7/31/25), where a corrupted value would have generated phantom ramp events large enough to consume an entire K-Means cluster (see Appendix A).

Seasons are mapped as: Summer = June–September, Winter = December–February, Shoulder = March–May and October–November. A note on naming: EIA-930 identifies CAISO by the code "CISO," and some figures retain that code; the text uses CAISO throughout.

---

## 3. Measuring Daily Grid Stress

Each day is scored on two components: daily peak load (Z_DPL) and daily maximum hourly ramp (Z_MHR). Both are z-scored within each BA across the full year (equation 1), then added with equal weights to form the composite stress score (equation 2). A zero means a typical day. For dashboard display, the composite is additionally min-max scaled within each BA to a 0–1 index (equation 3).

```
Z = (X − μ) / σ        where μ is the annual mean and σ the standard deviation    (eq. 1)

stress_z = Z_DPL + Z_MHR                                                          (eq. 2)

stress_01 = (stress_z − Z_min) / (Z_max − Z_min)                                  (eq. 3)
```

The within-BA standardization is what makes cross-system comparison valid even though the two grids differ in absolute scale by roughly 4× (CAISO's 2025 mean daily peak was ~29.6 GW against PJM's ~109.2 GW). A value of +1.0 means "one standard deviation above that system's own average" in both systems.

Two candidate components were evaluated and deliberately excluded:

- **Daily energy (MWh)** correlates with daily peak at r = 0.92–0.95 and would have double-counted the load signal. It is retained as an output column but excluded from scoring and clustering.
- **A duration term was tested and rejected.** The previous edition of this report included a third component — the fraction of hours near the daily peak. Systematic re-evaluation of five candidate duration metrics showed that relative-to-peak formulations measure load-profile *shape* rather than severity (extreme days have spiky profiles, so few hours sit near the daily max, and the metric ends up negatively correlated with stress — the inverse of intent), while annual-percentile formulations are redundant with peak load at r > 0.80. A physically meaningful duration metric would need an absolute reference tied to operating headroom — hours above the day-ahead reserve margin, or above a fraction of nameplate capacity — and neither is available in EIA-930. The exclusion is a documented data-availability constraint, not a methodological surrender. The full justification table is in Appendix A.

One known limitation of the additive formula is worth naming up front: it can produce near-zero scores for a high-peak / low-ramp day. In practice such days are rare — the two components correlate at r = 0.65 — but the index is not designed to flag isolated capacity-only stress (see Section 8).

**Figure 1. Daily grid stress time series.** Daily stress_01 for CAISO and PJM over calendar year 2025. Both systems peak in summer; CAISO's stress is more concentrated seasonally while PJM builds earlier and holds longer. Counting high-stress days (stress_01 > 0.7), PJM logged 46 to CAISO's 18.

![Figure 1](reports/figures/stress_daily/stress_timeseries_stacked.png)

---

## 4. Operating Regimes

K-Means clustering (k = 4, run independently per BA) classifies every day of 2025 into one of four operating regimes. The feature matrix is deliberately minimal — just the two standardized score components, [z_peak, z_ramp] — so the regimes are directly interpretable in the same space the stress index lives in. The previous edition clustered on five PCA-reduced features; the redesign trades a little geometric nuance for a model an operator can read off a 2-D scatter plot.

The choice of k = 4 is supported by a multi-metric sweep (silhouette, Davies-Bouldin, Calinski-Harabasz across k = 2–8; see Appendix B). At k = 4, silhouette = 0.398 (CAISO) and 0.407 (PJM) with Davies-Bouldin of 0.86 and 0.85 — and, more importantly, k = 4 is consistent across both BAs and maps onto an operationally legible ladder: **Stable → Moderate → Elevated → Extreme**. Labels are assigned automatically at runtime from cluster properties (rank by mean stress), so re-running the pipeline never requires manual relabeling.

**Table 1. CAISO operating regimes (365 days).**

| Regime | Days | % of year | Mean stress_z | Max stress_z | Season mix |
|---|---|---|---|---|---|
| Stable | 160 | 44% | −1.48 | −0.22 | Shoulder 68%, Winter 27%, Summer 6% |
| Moderate | 108 | 30% | +0.10 | +2.05 | Winter 44%, Shoulder 37%, Summer 19% |
| Elevated | 65 | 18% | +1.42 | +3.06 | Summer 92%, Shoulder 8% |
| Extreme | 32 | 9% | +4.13 | +6.60 | Summer 100% |

**Table 2. PJM operating regimes (365 days).**

| Regime | Days | % of year | Mean stress_z | Max stress_z | Season mix |
|---|---|---|---|---|---|
| Stable | 89 | 24% | −2.18 | −0.96 | Shoulder 69%, Winter 20%, Summer 11% |
| Moderate | 110 | 30% | −0.20 | +1.59 | Shoulder 76%, Winter 13%, Summer 11% |
| Elevated | 96 | 26% | +0.28 | +1.42 | Winter 46%, Summer 46%, Shoulder 8% |
| Extreme | 70 | 19% | +2.71 | +4.83 | Summer 80%, Winter 20% |

The same four-tier ladder shows up in both systems, but its proportions tell the structural story. CAISO spends 44% of the year in Stable and just 9% in Extreme — but that Extreme regime averages +4.13σ, is 100% summer, and tops out at z = 6.60. PJM spends only 24% of the year in Stable and a full 19% in Extreme, but its Extreme regime averages a more moderate +2.71σ. CAISO concentrates its stress into a small, violent window; PJM accumulates it steadily across a longer season and two physical mechanisms (heat and cold).

**Figure 2. Operating regimes in feature space.** Daily peak load z-score vs. daily max ramp z-score, colored by cluster, for CAISO (left) and PJM (right). Both systems' Extreme regimes occupy the upper-right — elevated peak and elevated ramp simultaneously — but CAISO's extends much further out.

![Figure 2](reports/figures/storytelling/01_regimes_feature_space/regimes_feature_space_combined.png)

**Figure 3. Stress distributions by regime.** Stress_z by cluster, ordered by mean stress. Both BAs show a clean four-tier progression with well-separated low and high ends. CAISO's Extreme box sits far above everything else; PJM's tiers are more evenly spaced.

![Figure 3](reports/figures/storytelling/02_stress_by_cluster/02_stress_by_cluster_combined.png)

**Figure 4. Regime frequency vs. mean stress.** Mean stress per regime against the share of days spent in it. CAISO's Extreme regime is rare (~9% of days) but acute at +4.1σ; PJM's is more frequent (~19%) and more moderate at +2.7σ.

![Figure 4](reports/figures/storytelling/03_frequency_vs_stress/03_frequency_vs_stress_combined.png)

**Figure 5. Cluster seasonal composition.** How each regime maps to Summer / Shoulder / Winter. CAISO's Extreme regime is purely a summer phenomenon. PJM's Extreme regime is 80% summer / 20% winter, and its Elevated regime splits almost evenly between winter (44 days) and summer (44 days).

![Figure 5](reports/figures/storytelling/appendix_hourly/A3_cluster_seasonal_composition.png)

Two observations from the regime structure deserve emphasis.

**The within-BA stress magnitude is itself a finding.** CAISO extreme days reach ~4σ above CAISO's own mean; PJM extreme days reach only ~2σ above PJM's. Since the z-scores are computed within each BA, this is substantive rather than a scaling artifact: CAISO operates a tightly distributed regime that occasionally breaks violently, while PJM's day-to-day operating range is wide enough that even its worst days are less anomalous in normalized terms. This reinforces the acute-vs-broad narrative without requiring any additional measurement.

**A regime label alone is not sufficient operational characterization for PJM.** PJM's Elevated regime contains 46% winter days and 46% summer days — physically different stress (cold-snap morning heating spikes vs. heat-dome afternoon peaks) sharing one statistical signature. Season context has to ride along with the label, which is why the dashboard exposes both through a season slicer.

---

## 5. Extreme Stress Events

### 5.1 Two-tier event extraction

Event analysis starts from cluster membership: candidate days are drawn from a regime's cluster, filtered by a season-specific stress floor, and reduced to independent events by enforcing a minimum 14-day separation between event peaks (the highest-stress day of any overlapping episode is kept). Each event then gets a −7/+14 day window for trajectory analysis.

Running this only on the Extreme regime misses PJM Winter almost entirely — at k = 4 with this feature set there is no winter-dominated cluster, and the worst cold snaps (z ≈ 2.3) sit well below PJM's summer extremes (z ≈ 4.8). Rather than complicate the clustering with season-stratified models, the pipeline extracts events at **two severity tiers** — Extreme and Elevated — per (BA × season). The Elevated tier uses permissive stress floors precisely so that physically meaningful but statistically milder events, like PJM's winter cold snaps, surface alongside the summer extremes.

**Table 3. Independent extreme events by BA, season, and tier (2025).**

| BA × Season | Extreme tier | Elevated tier |
|---|---|---|
| CAISO Shoulder | 0 | 2 |
| CAISO Summer | 4 | 6 |
| PJM Summer | 4 | 6 |
| PJM Winter | 3 | 5 |

The top PJM Winter events — Jan 23 (z = 2.34), Dec 14 (z = 2.29), and Feb 18 (z = 1.91) — are exactly the polar-vortex and cold-snap episodes that operator records confirm (Section 6). Capturing them without touching the clustering keeps the regime model simple and pushes the seasonal nuance into the event layer, where it belongs.

**Figure 6. Composite extreme-event trajectories (summer events).** Mean stress, peak-load z, and max-ramp z relative to the event peak (day 0), averaged across each BA's Extreme-tier summer events; shading is ±1 SD across events. CAISO builds for about a week and spikes hard at day 0; PJM's buildup and recovery are slower and more symmetric.

![Figure 6](reports/figures/storytelling/05_event_composite/05_composite_trajectory.png)

### 5.2 CAISO: a two-stage compound mechanism

CAISO's extreme events are summer heat waves with a consistent anatomy: several days of temperature buildup elevate load, and then the evening solar drop-off converts elevated load into a catastrophic net-load ramp. The regime framework records this as a single Extreme classification, but operationally it is a *sequence* — a load stage and a ramp stage — and the trigger is the second stage. On the rank-1 stress day of 2025 (September 3, z = 6.60), solar generation displaced midday demand down to an 18.7 GW net-load trough at 2 PM, then handed back ~7.5 GW in a single hour as the sun set into the evening peak (Figure 7). With solar at roughly 25% of CAISO generation, this duck-curve dynamic adds a ramp component that is partially decoupled from demand itself — which is why CAISO extremes require *both* components elevated simultaneously.

**Figure 7. Solar duck curve on CAISO's peak stress day (Sept 3, 2025).** Gross demand, solar generation, and net load (top); hourly net-load ramp rate (bottom). The evening ramp window shows demand rising as solar collapses — +7.5 GW/hr at 8 PM.

![Figure 7](reports/figures/storytelling/appendix_hourly/A1_ciso_duck_curve.png)

### 5.3 PJM: load-led in two seasons

PJM's summer extremes are heat-dome events: sustained high demand across a large footprint, building slowly (~a week) and receding at nearly the same pace, with ramp tracking load and little day-to-day volatility. Its winter extremes behave differently — cold snaps drive demand up within one to two days, the stress signature is a sharp *morning* heating spike rather than a sustained afternoon peak, and the ramp component is weak or negative (Figure 8). Two physically distinct mechanisms, both load-led, both captured by the same index.

**Figure 8. PJM hourly demand profile, summer vs. winter extreme days.** June 24 (rank-1 summer event, z = 4.83): a gradual morning ramp into a sustained afternoon peak. January 23 (top winter day, z = 2.34): a sharp pre-dawn heating spike as thermostats hit at the coldest hour.

![Figure 8](reports/figures/storytelling/appendix_hourly/A2_pjm_summer_vs_winter.png)

### 5.4 Event anatomy: onset timing

Within event windows, the components cross their onset threshold (z ≥ 1.0) at characteristic lead times before the stress peak: peak load first, max ramp later. For Extreme-tier events, mean onsets are CAISO Summer −5.5 / −4.0 days (load / ramp), PJM Summer −6.5 / −4.5, and PJM Winter −3.5 / −2.5 — the winter numbers confirming that cold snaps come on roughly twice as fast as heat events (Figure 9).

To be clear about what this is: **descriptive event anatomy, not a forecast horizon.** Both components are downstream of the same temperature trajectory that operators already track directly through weather forecasts. The lead-lag describes how events unfold; it does not provide warning that weather data wouldn't provide earlier and better.

**Figure 9. Event onset lead time by regime and stress tier.** Days before the stress peak at which each component crosses z ≥ 1.0, by BA × season × tier.

![Figure 9](reports/figures/storytelling/page3/S1_onset_timing.png)

### 5.5 Recovery variance and event clustering

Recovery — days from the stress peak back to z < 1.0 — varies more than severity alone explains. CAISO summer events take 6–10 days, with the severity gradient holding (worse events take longer). PJM summer events recover faster, in 3–9 days, but same-severity events recover at visibly different rates within each BA (Figure 10). That spread suggests a second axis the current index doesn't measure — weather persistence is the obvious candidate, with antecedent conditions and system reset speed as alternatives. It's flagged here as a research question rather than a finding.

PJM's summer events also arrive tightly packed: several 2025 event windows were truncated by the *next* event arriving before recovery completed (visible as ✕ markers in Figure 10). Where CAISO's events are discrete episodes, PJM's can overlap — a cumulative-stress risk that single-event statistics understate.

**Figure 10. Post-peak recovery by event (summer events).** Stress index from the event peak forward, per event. Circles mark recovery (z < 1.0); ✕ marks windows truncated by the next event. CAISO recoveries run 6–10 days with severity ordering intact; PJM runs 3–9 days with several truncated windows.

![Figure 10](reports/figures/storytelling/05_event_composite/05_event_recovery.png)

---

## 6. External Validation: Operator Alerts

As a first-pass external check, every 2025 day was cross-referenced against operator-issued alerts: CAISO's Grid Emergencies History report (all alert types — Flex Alerts, EEAs, RMOs, transmission emergencies) and PJM's Hot Weather / Max Generation Alerts and Cold Weather Alerts compiled from PJM's press releases and cold-weather operations reviews. This is a preview of a proper validation effort, not a substitute for one — the caveats are listed in Appendix C.

### 6.1 PJM: strong precision in both seasons

**Table 4. PJM 2025: operator alert-days by model regime.**

| Regime | Days | Days with operator alert | % |
|---|---|---|---|
| Stable | 89 | 3 | 3.4% |
| Moderate | 110 | 2 | 1.8% |
| Elevated | 96 | 1 | 1.0% |
| **Extreme** | **70** | **21** | **30.0%** |

Of PJM's 27 operator alert-days in 2025, **21 (78%) landed in the model's Extreme regime** — and the precision holds equally for summer heat-driven and winter cold-driven alerts. That seasonal consistency is the strongest cross-validation evidence for the two-tier event approach: the model classifies the right days as Extreme across both physical mechanisms without any season-specific tuning.

Recall runs the other direction: only 13% of model-flagged high-stress days carried an operator alert. That is expected rather than concerning — PJM issues alerts based on reserve forecasts for a subset of stressed days, not on every day that is physically demanding.

### 6.2 CAISO: a striking null result

**Zero CAISO operator alerts fell on any of the 32 model-flagged Extreme days — including the top five stress days of the year (z = 6.60 down to 5.24).** CAISO issued no Flex Alerts and no Energy Emergency Alerts at all in 2025; the only declarations were one restricted-maintenance operation (January fire weather) and one transmission emergency (April, Rio Oso line). The summer the model classifies as acute and ramp-amplified passed without a single operator emergency.

Three interpretations, none mutually exclusive:

1. **CAISO's supply margin caught up.** Storage and capacity additions since the 2020/2022 emergency years have decoupled load stress from reserve shortfalls.
2. **The model measures demand-side physical stress, not supply adequacy.** stress_z captures peak load and max ramp; CAISO's alerts trigger on reserve shortfall. With sufficient capacity, the two decouple.
3. **The alert frameworks differ structurally.** Flex Alerts are conservation appeals, not reserve declarations — the bar for issuing one is different from PJM's alert ladder.

The honest framing is both-and: this is a real model limitation — **the index is a load/ramp diagnostic, not a reserve-margin forecaster** — and it is a substantive finding. The same physical-stress instrument maps onto operator action in one system (30% of PJM Extreme days alerted) and not at all in the other (0%), which is concrete external evidence for the "different physics, different responses" conclusion the internal analysis already pointed to.

One coverage gap worth recording: 7 of PJM's 14 winter Extreme days fell outside the compiled alert windows, but almost all sit 1–4 days adjacent to confirmed alert periods — most likely covered by PJM Cold Weather *Advisories* (the lower-tier precursor), which were not compiled in this pass. Adding them would likely raise PJM winter coverage from 50% to 90%+ and would only strengthen the precision number.

**Figure 11. Daily stress with operator alert days overlaid.** Model-flagged Extreme-regime days (markers) against operator alert windows (shaded bars) for CAISO (top) and PJM (bottom), 2025. PJM's alert windows line up with the model's extreme episodes in both summer and winter; CAISO's chart has essentially no bars to line up with.

![Figure 11](Insights/sneak_peek_validation/stress_with_alerts.png)

---

## 7. The Dashboard

The shipped deliverable is a three-page Power BI dashboard built on the pipeline's exported tables. All z-score math is reimplemented in DAX against Python-exported reference constants (per-BA means, standard deviations, and cluster centroids), and the DAX classification logic is validated against the reference Python implementation.

**Page 1 — Overview** (Figure 12). The daily stress_01 line, average stress by month decomposed into its z-peak and z-ramp components, and a 30-day rolling count of high-stress days, alongside per-BA KPI cards (max stress, average stress, most stressed day, high-stress day count) and a most-stressful-days table. The rolling count makes the structural contrast legible at a glance: CAISO's high-stress days pile into a tight August–September window while PJM's build earlier and hold longer.

![Figure 12](reports/dashboard/Grid-Stress-Analysis_Dashboard_p1.png)

**Page 2 — ML Clustering** (Figure 13). The regime scatter in z-score space, cluster frequency and per-cluster average z-scores, days by cluster and season, and the k-selection silhouette table. This page also hosts the **Daily Stress Calculator**: an operator enters a peak-load and max-ramp value in MW, and the dashboard returns the classified regime and stress percentile live. Verified against the reference implementation: CAISO 40,000 MW / 3,000 MW → Extreme, 94th percentile; PJM 100,000 MW / 7,000 MW → Moderate, 62nd percentile.

![Figure 13](reports/dashboard/Grid-Stress-Analysis_Dashboard_p2.png)

**Page 3 — Event Drilldown** (Figure 14). Three composite-event panels — CAISO Summer (ramp-amplified, ~4σ peaks), PJM Summer (load-dominated, ~2σ), PJM Winter (load-dominated cold snaps, ~1σ) — with lead-day bars by BA × season × component and hourly demand/ramp views for extreme days. The y-axes on this page are intentionally independent across panels: the page is about event *anatomy* (shape and lead-lag), and forcing a shared scale would flatten the PJM panels into illegibility. The magnitude story is told on Page 1's KPI cards — and, per Section 4, the within-BA magnitude difference is itself a finding rather than something to normalize away.

![Figure 14](reports/dashboard/Grid-Stress-Analysis_Dashboard_p3.png)

---

## 8. Limitations

Naming these well matters more than minimizing them.

1. **The model is a diagnostic, not a simulator or forecaster.** It characterizes observed stress; it cannot answer counterfactuals ("what if 5 GW of solar were added?") without a bottom-up load/capacity model.
2. **It measures demand-side physical stress, not reserve adequacy.** Section 6.2 is the concrete demonstration: CAISO's reserve position decoupled physical stress from operator action in 2025.
3. **The additive formula can miss isolated capacity-only stress.** A high-peak / low-ramp day can score near zero. Rare in practice (component correlation r = 0.65), but real.
4. **Single-year sample.** 2025 only. Regime structure and event statistics may not generalize across years; cross-validation against 2020–2022 — especially for CAISO, when alerts were frequent — is the natural next test.
5. **No economic ground truth yet.** LMP correlation is the strongest next validation; OE-417 incident data is the sharpest precision check.
6. **Within-BA z-scores are not directly comparable across BAs in absolute terms.** A CAISO 4σ day and a PJM 2σ day are extreme *relative to their own systems*. The report and dashboard handle this explicitly (independent axes, within-BA framing), but any cross-BA magnitude comparison needs that caveat attached.
7. **Cluster labels are auto-derived from rank, not anchored to physical thresholds.** Robust across re-runs, but "Extreme" means "this BA's highest-stress regime," not "above X MW" — operator interpretation requires per-BA context.

---

## 9. Next Steps

In rough priority order:

1. **Weather-driven regime prediction.** Given a multi-day temperature forecast (plus humidity, cloud cover, wind), predict tomorrow's regime classification. The regime framework supplies categorical decision boundaries; weather forecasts carry skill out 7+ days; combining them yields a categorical risk forecast aligned with how operators already consume weather information. This — not the within-event component lead-lag — is the operationally valuable forecasting opportunity.
2. **LMP correlation.** Pull hourly locational marginal prices (PJM Data Miner 2, CAISO OASIS) and correlate daily peak-price percentiles against stress_z for an economic anchor that doesn't depend on an operator declaring anything.
3. **Temperature sensitivity slopes.** Regress stress_z on weather features to get "+1°C summer max temperature = +X stress_z," which converts directly into a one-page climate deliverable: "+2°C warming ≈ +N extreme days per year."
4. **Multi-year backtest**, especially CAISO 2020–2022, when Flex Alerts and EEAs were frequent — the validation that 2025 couldn't provide.
5. **Scenario analysis** (data centers, solar additions, retirements) — with honesty that this requires a bottom-up demand/capacity model. A tractable middle ground: detrend observed load and re-inflate under hotter temperature scenarios.
6. **Compile PJM Cold Weather Advisories** to close the winter validation coverage gap.

---

## 10. Conclusion

The framework delivers a clean, reproducible way to classify grid operating states from public data — and applying the same instrument to two systems is what surfaces the real finding. CAISO and PJM do not just experience different amounts of stress; they experience *different stress*. CAISO's is rare, acute, and ramp-amplified by the duck curve's two-stage mechanism; PJM's is frequent, broad, load-led, and arrives through two distinct seasonal channels. The external alert record sharpens rather than blurs that contrast: PJM's operator actions concentrate almost perfectly in the model's Extreme regime, while CAISO's reserve position has decoupled operator action from physical stress entirely.

The instrument re-runs without maintenance, extends to any EIA-930 balancing authority, and ships with an operator-facing front end. What it doesn't yet do is predict — and the regime labels it produces are precisely the targets a weather-driven forecast model needs. That is the next version of this work.

---

## Appendix A: Stress Score Construction and the Duration Question

All features are computed from hourly EIA-930 demand readings aggregated to the calendar day, independently per BA:

- **Daily Peak Load (MW):** maximum hourly demand reading in the day.
- **Daily Maximum Hourly Ramp (MW/hr):** largest absolute change in demand between consecutive hourly readings. Sign is dropped — up-ramps and down-ramps count equally.
- **Daily energy (MWh)** is computed and retained as an output but excluded from scoring and clustering (r = 0.92–0.95 with daily peak).

Z-scores use the full-year population standard deviation (ddof = 0) within each BA. The 2025 reference constants — also exported for the dashboard's DAX implementation — are:

| BA | Feature | Mean | Std |
|---|---|---|---|
| CAISO | daily_peak_mw | 29,562 | 4,313 |
| CAISO | daily_max_ramp_mw | 2,383 | 635 |
| PJM | daily_peak_mw | 109,157 | 17,698 |
| PJM | daily_max_ramp_mw | 5,749 | 1,360 |

**The duration evaluation.** Five candidate duration metrics were tested for inclusion as a third component. All failed for one of two reasons, documented in Table A1:

- **Relative-to-peak metrics** (% of hours within 95% or 85% of that day's own peak) measure load-profile shape, not severity. Extreme days have spiky profiles where few hours sit near the daily max, while ordinary flat-load days score high — producing *negative* correlation with stress, the inverse of intent.
- **Annual-percentile metrics** (% of hours above the BA's annual P90 or P75) correlate positively with stress, but at r > 0.80 with z_peak they merely double-count the peak signal.

**Table A1. Duration metric justification (correlations with stress components).**

| BA | Duration metric | r vs. daily peak | r vs. z_peak | r vs. stress_z |
|---|---|---|---|---|
| CAISO | % hours ≥ 95% of daily peak | −0.23 | −0.23 | −0.21 |
| CAISO | % hours ≥ 85% of daily peak | −0.47 | −0.47 | −0.41 |
| CAISO | % hours above annual P90 | 0.90 | 0.90 | 0.84 |
| CAISO | % hours above annual P75 | 0.93 | 0.93 | 0.86 |
| CAISO | Smooth multiplier z* = z_pct × max(0, z_peak) | −0.74 | −0.74 | −0.70 |
| PJM | % hours ≥ 95% of daily peak | −0.15 | −0.15 | −0.12 |
| PJM | % hours ≥ 85% of daily peak | −0.37 | −0.37 | −0.40 |
| PJM | % hours above annual P90 | 0.81 | 0.81 | 0.72 |
| PJM | % hours above annual P75 | 0.87 | 0.87 | 0.73 |
| PJM | Smooth multiplier z* = z_pct × max(0, z_peak) | −0.09 | −0.09 | −0.11 |

A duration metric that measured what matters operationally — *time spent without headroom* — would need an absolute reference such as hours above the day-ahead reserve margin or above ~95% of nameplate capacity. Neither exists in EIA-930, so the score remains two-component by constraint, not by preference.

**Figure A1. Unfiltered (top), filtered z-score (middle), and filtered min-max (bottom) stress time series.** The unfiltered top panel shows the late-July CAISO reporting artifact spiking to 1.0 and compressing every other day toward zero — the motivation for the hourly spike filter. The middle panel preserves cross-BA z-magnitude; both systems operate within a comparable range, confirming min-max scaling does not distort the comparison.

![Figure A1](reports/figures/stress_daily/stress_timeseries_appendix.png)

**Figure A2. Distribution of daily stress scores.** Roughly symmetric with a right tail; CAISO's upper tail extends further (to z = 6.6) while PJM's distribution is wider through the middle — the distributional signature of the acute-vs-broad contrast.

![Figure A2](reports/figures/stress_daily/stress_distribution.png)

## Appendix B: Clustering Details and k Selection

Clustering is K-Means (k = 4, random_state = 42, n_init = 20), fit independently per BA on the feature matrix [z_daily_peak_mw, z_daily_max_ramp_mw]. No StandardScaler is applied (the features are already z-scored) and no PCA (two features, no collinearity to remove — daily energy was excluded for exactly that reason).

k was selected with a sweep over k = 2–8 evaluating silhouette, Davies-Bouldin, and Calinski-Harabasz, plus the seasonal concentration of the resulting clusters:

**Table B1. k-sweep metrics (selected rows).**

| BA | k | Silhouette | Davies-Bouldin | Calinski-Harabasz |
|---|---|---|---|---|
| CAISO | 2 | 0.511 | 0.79 | 449 |
| CAISO | 3 | 0.398 | 0.88 | 412 |
| **CAISO** | **4** | **0.398** | **0.86** | **409** |
| CAISO | 5 | 0.376 | 0.86 | 394 |
| CAISO | 6 | 0.372 | 0.84 | 394 |
| PJM | 2 | 0.420 | 0.88 | 371 |
| PJM | 3 | 0.411 | 0.85 | 435 |
| **PJM** | **4** | **0.407** | **0.85** | **430** |
| PJM | 5 | 0.387 | 0.81 | 438 |
| PJM | 6 | 0.414 | 0.76 | 461 |

No k dominates on the metrics alone — k = 2 maximizes silhouette but collapses the operating range into "calm vs. not," and PJM's k = 6 wins Davies-Bouldin but fragments the moderate range without adding operational meaning. k = 4 was chosen because it is consistent across both BAs, the metric costs relative to neighbors are small, and four tiers map cleanly onto an operator-legible Stable → Moderate → Elevated → Extreme ladder. Chasing winter regime separation at higher k was considered and rejected; the two-tier event extraction (Section 5.1) handles PJM Winter without complicating the regime model.

**Auto-labeling.** Cluster integer IDs are arbitrary and shift between runs. Labels are therefore derived at runtime from cluster properties — clusters are ranked by mean stress_z and assigned Stable / Moderate / Elevated / Extreme in order — and the extreme-cluster lookup used by event extraction is derived the same way. Re-running the pipeline can renumber clusters freely without breaking labels, event extraction, or the dashboard.

**Figure B1. Cluster quality metrics across k.** Silhouette, Davies-Bouldin, and Calinski-Harabasz for k = 2–8, both BAs, with the chosen k = 4 marked.

![Figure B1](reports/figures/k_sweep/cluster_quality_metrics.png)

## Appendix C: Supplementary Notes

**C.1 — Changes from the previous edition.** This report supersedes *Electric Grid Fragility Analysis* (January 2026, revised April 2026). The substantive changes: (1) "fragility" was renamed to "stress" — the index measures how hard a system is being worked, not how close it is to breaking, and the old name overclaimed; (2) the near-peak persistence component was removed from the composite after the duration evaluation (Appendix A) showed it measured profile shape rather than severity; (3) clustering now runs directly on the two standardized score components rather than PCA-reduced five-feature space, trading geometric nuance for interpretability; (4) cluster labels are now auto-derived, making re-runs maintenance-free; (5) two-tier event extraction was added, bringing PJM Winter into the event analysis; (6) the external alert validation and the Power BI dashboard are new.

**C.2 — Solar penetration.** Solar accounts for roughly 25% of CAISO's generation versus roughly 5% for PJM, which is the structural driver behind their different ramp physics via the duck curve.

**C.3 — One year of data.** 365 days per BA characterizes seasonal structure and repeatable regime patterns but cannot assess inter-year variability. Grid composition is moving quickly — solar growth, electrification, data-center load — so regimes should be retrained, not assumed, for other years.

**C.4 — Validation caveats.** Alert dates were hand-compiled: PJM's from a press-release feed (not an exhaustive log) and cold-weather operations reviews, CAISO's from its Grid Emergencies History report (rev. 04/2026). Alerts lasting a few hours are flagged as whole days, which overstates coverage on short events. PJM Cold Weather Advisories (the tier below Alerts) were not compiled; Section 6.2 estimates their impact. Several candidate PJM articles were 2026 events and were excluded after date verification.

**C.5 — Reproducibility.** The full pipeline runs end-to-end via make (`make pipeline`, then `make event_composite`), and every figure and table in this report regenerates from raw EIA-930 input without manual steps. Per-BA models, self-calibrating data repair, and auto-labeled clusters mean adding a new balancing authority or year is a configuration change, not new code.

---

*Data source: U.S. Energy Information Administration, EIA-930 Hourly Electric Grid Monitor, 2025. https://www.eia.gov/electricity/gridmonitor/*
