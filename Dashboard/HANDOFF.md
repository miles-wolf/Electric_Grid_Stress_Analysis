# Power BI Dashboard — Handoff Brief

Pick up the grid fragility dashboard work in Claude Desktop. Full project context is in `../CLAUDE.md`. This file captures dashboard-specific state and decisions from the prior Claude Code session.

---

## Where Things Stand

The dashboard is mid-rebuild after the clustering redesign. The Python pipeline was changed to drop PCA / `PC1` and use raw z-scores (`z_daily_peak_mw`, `z_daily_max_ramp_mw`) for clustering. Page 2 (cluster overview) is functional. Page 3 is planned but not started.

**.pbix location:** `C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis\Dashboard\grid_fragility_anlaysis_dashboard - Copy.pbix`

---

## Data Tables Loaded into Power BI

| Table | Source CSV |
|---|---|
| `daily_stress_pjm_ciso_2025` | `data/processed/stress/daily_stress_pjm_ciso_2025.csv` |
| `daily_with_clusters` | `data/processed/unsupervised/daily_with_clusters.csv` |
| `top_days_table` | `reports/figures/stress_daily/top_days_table.csv` |
| `date_table` | (date dimension built in Power BI) |

All three CSV-backed queries were rebuilt with minimal M code (Advanced Editor) + explicit `Table.TransformColumnTypes` to fix two problems the prior load had:
1. `Choose Columns` / `Removed Other Columns` steps were whitelists from an older schema, dropping new columns silently.
2. Auto-typing left numeric columns as text → only Count was available, not Average.

The M code for each table is the standard pattern: `Csv.Document → PromoteHeaders → TransformColumnTypes` listing every column explicitly. If columns are added upstream, those `TransformColumnTypes` lists need updating.

---

## Fixes Already Applied

1. **Jan 1 2026 data check** — investigated whether the parquet file at `data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet` contained Jan 1 2026 rows. Found 15 rows with `timestamp_utc` on 2026-01-01, but all have `data_date = 12/31/2025` (they're Dec 31 local time expressed in UTC because CISO is UTC-8 and PJM is UTC-5). **No deletion needed.** The pitfall is binning on `timestamp_utc.dt.date` in Power BI — that creates a phantom Jan 2026 bucket. Use `data_date` or `local_time_at_end_of_hour` for date binning instead.

2. **`PC1` references broke after pipeline redesign** — the new clustering uses `z_peak` + `z_ramp` only, so `PC1` no longer exists. All measures/visuals referencing `PC1` had to be re-pointed manually to `z_daily_peak_mw` / `z_daily_max_ramp_mw` / `stress_z` depending on intent.

3. **Most Fragile Day KPI card showed three categories** — a phantom "(Blank)" row with `--`. Raw data is clean (only CISO and PJM, no nulls). Cause is almost certainly a relationship issue (Power BI's "(Blank)" row pattern when grouping by a column from one table but the measure pulls from a related table with unmatched keys). Masked with a visual-level filter `balancing_authority is not blank`. The same fix should be applied to the BA slicer on Page 2 — it still shows "(Blank)".

4. **Date binning broke after linking `daily_stress[date]` to `date_table`** — expected. Linking a fact column to a date dimension disables the auto date hierarchy on the fact column. Fixed by swapping `daily_stress[date]` → `date_table[Month]` on visual axes. **Same swap still needs to happen on any other visual that was bucketing by month on a raw fact-table date.**

---

## Page 2 — Current State

Page 2 is the cluster overview. Current visuals:
- Scatter: `z_daily_peak_mw` vs `z_daily_max_ramp_mw` colored by cluster
- Donut: count of dates per cluster
- Horizontal grouped bar: average z-scores by cluster (four series)
- BA slicer (single-select, still has "(Blank)" option visible)

### Recommended polish before adding the cluster identifier tool

1. **Use `cluster_label` instead of `cluster` everywhere.** The data has labels (Extreme / Moderate ramp+peak / Moderate duration / Stable per BA — see CLAUDE.md). Right now everything's labeled 0/1/2/3, which forces operators to mentally translate.
2. **Remove "(Blank)" from the BA slicer** — same `is not blank` filter as the KPI card.
3. **Bottom bar chart needs work:**
   - Legend labels are truncated (four "Average of z_daily..." overlapping). Rename the measures to short names (e.g. `Peak z`, `Ramp z`, `Stress z`, `Stress (0–1)`).
   - Four overlapping series per cluster is a lot. Consider splitting into two charts (z-components vs. stress composites) or pivoting to a heatmap of cluster × feature.

---

## Next Up — Cluster Identifier Tool (Page 2)

Goal: let a grid operator input current conditions and see which cluster the day falls into, plus how it compares to historical extremes.

**Suggested design:**
- Two numeric input slicers: `z_peak`, `z_ramp`
- Card: which cluster the (peak, ramp) point falls into (nearest-centroid assignment)
- Card or table: historical comparison — e.g., percentile within that cluster, how many days have been more extreme

**Implementation note:** the cluster centroids live in `data/processed/unsupervised/cluster_centroids_2025.csv`. Load that as another table, then a DAX measure can compute Euclidean distance from the input point to each centroid and return `MINX`. Per-BA models, so the centroids table has rows per `(balancing_authority, cluster)`.

---

## Page 3 — Planned

Diagnostic deep-dive page. Will house:
- **Lead/lag time analysis** — onset timing for peak load, max ramp, and duration components (data in `data/processed/event_composite/event_onset.csv`)
- **Temporal trajectories** — composite event windows showing how fragility builds before peak (data in `data/processed/event_composite/event_composite.csv` and `event_windows.csv`)

Key context from CLAUDE.md to drive the storytelling:
- **CISO summer:** load builds ~7 days before peak; solar evening drop-off is the trigger
- **PJM summer:** ~6 days build-up (heat wave)
- **PJM winter:** ~1 day build-up (polar vortex) — fundamentally different dynamic, must be kept seasonally separate

These three regimes deserve visual differentiation on the page.

---

## Pitfalls to Avoid in Future Edits

- **Don't re-add `Choose Columns` / `Removed Other Columns` steps** to the CSV queries unless you really need to drop columns. They silently break on schema changes.
- **Don't bin dates on `timestamp_utc.dt.date`** — it creates a phantom Jan 2026 bucket from Dec 31 local data. Always bin via `date_table[Month]` (or `data_date` / `local_time_at_end_of_hour` if going direct).
- **Cluster numbers (0–3) will shift on every clustering rebuild.** Reference `cluster_label` in visuals, not `cluster`, so reruns don't silently scramble the legend.
- **When linking a fact column to `date_table`**, the fact column's auto date hierarchy goes away — expected. Re-point all month/year bucketing to `date_table` columns.
