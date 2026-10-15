# Grid Stress Analysis — Power BI → Tableau Migration Guide

A faithful 1:1 rebuild of the finished 3-page Power BI dashboard
(`Dashboard/Grid-Stress-Analysis_Dashboard.pbix`, Jun 10 2026 render) in Tableau Desktop.

Everything the Power BI version does is reproduced here: the same visuals, the same
KPI logic, the **Daily Stress Calculator** (nearest-centroid what-if tool), and the
Event Drilldown page. All custom DAX has been translated to Tableau calc syntax and
number-matched against the live dashboard (see the ✓ checks below).

---

## 0. How to use this guide

1. Connect the 7 staged CSVs in `tableau/data/` (§1).
2. Create the 3 parameters (§2).
3. Create the calculated fields (§3) — copy/paste the formulas verbatim.
4. Build each worksheet (§4–6), then assemble the 3 dashboards (§7).

A companion starter workbook, `Grid-Stress-Analysis.twb`, ships with the data
connections, parameters, and calculated fields **pre-defined** so you can skip the
typing in §2–§3 and go straight to dragging fields onto shelves. Spot-check the calc
fields against §3 after opening.

---

## 1. Data sources

Connect each CSV as a **Text file** connection (`Data > New Data Source > Text file`).
Keep them as **separate data sources** — Tableau uses one primary source per worksheet,
and these pages don't need cross-source joins (blending notes called out where relevant).

| Data source (rename to) | File | Feeds |
|---|---|---|
| `daily_stress` | `data/daily_stress.csv` | Page 1 (all), Page 2 scatter/donut/bar, Calculator percentile |
| `top_days` | `data/top_days.csv` | Page 1 "Most Stressful Days" table |
| `page3_data` | `data/page3_data.csv` | Page 2 season-composition bar, Page 3 onset + composite lines |
| `hourly_peak_days` | `data/hourly_peak_days.csv` | Page 3 hourly demand + ramp |
| `k_selection` | `data/k_selection_summary.csv` | Page 2 silhouette table |
| `cluster_centroids` | `data/cluster_centroids.csv` | (reference; calculator hardcodes these) |
| `baseline_stats` | `data/baseline_stats.csv` | (reference; calculator hardcodes these) |

> **`daily_stress` is a superset** of the old Power BI `daily_stress_pjm_ciso_2025`
> table — it's `daily_with_clusters.csv`, which adds `cluster`, `cluster_label`,
> `ramp_dominant`. One table serves both Page 1 and Page 2, so you don't need the old
> `DateTable` dimension — Tableau's native date hierarchy on `[date]` replaces it.

**Type fixes after connecting `daily_stress`:**
- Set `date` → Date.
- Confirm `stress_01`, `stress_z`, `z_daily_peak_mw`, `z_daily_max_ramp_mw`,
  `daily_peak_mw`, `daily_max_ramp_mw` are **numbers (measures)**, not text.
  (This was the #1 Power BI load bug — same trap in Tableau if it auto-types as string.)
- `balancing_authority`, `season`, `cluster_label` → dimensions (strings).

**`page3_data` is a long/tidy table** keyed by a `record_type` column
(`onset` / `composite` / `composition` / `silhouette` / `centroid`). Each Page 2/3
visual that uses it gets a **data-source or worksheet filter on `record_type`** — this
is the Tableau equivalent of the Power BI visual-level `record_type=` filters.

---

## 2. Parameters

Create these three (right-click in Data pane > `Create Parameter`):

| Parameter | Data type | Allowable | Default |
|---|---|---|---|
| `Peak MW Input` | Float | All (or Range 0–200000) | `40000` |
| `Max Ramp MW Input` | Float | All (or Range 0–12000) | `3000` |
| `Calc BA` | String | List: `CISO`, `PJM` | `CISO` |

`Peak MW Input` and `Max Ramp MW Input` are the Power BI what-if slicers
("Peak Input (MW)" / "Max Ramp Input (MW)"). `Calc BA` replaces the role the Page 2
BA slicer played *for the calculator* — a Tableau parameter is global, so one control
drives the whole page. Show all three as controls on the Page 2 dashboard, and also add
a `Calc BA` filter action (or use `[balancing_authority] = [Calc BA]` as a filter) so
the BA choice filters the other Page 2 visuals too — matching the single-select BA
slicer behavior.

---

## 3. Calculated fields (the DAX translations)

Grouped by data source. Field names are suggestions — the starter `.twb` uses these exact names.

### 3a. On `daily_stress` — Page 1 KPIs

```
// Stress_Z (Max)  — KPI card, per BA.  CISO 6.60 / PJM 4.83 ✓
MAX([stress_z])
```
```
// Stress_01 (Avg) — KPI card, per BA.  CISO 0.31 / PJM 0.43 ✓
AVG([stress_01])
```
```
// Most Stressed Day — KPI card, per BA. CISO Sep 03 / PJM Jun 24 ✓
// (date of the BA's max stress_z; format the field as "mmm dd")
{ FIXED [balancing_authority] :
    MAX( IF [stress_z] = { FIXED [balancing_authority] : MAX([stress_z]) }
         THEN [date] END ) }
```
```
// High Stress Days — KPI card, per BA. Threshold stress_01 > 0.7. CISO 18 / PJM 46 ✓
SUM( IF [stress_01] > 0.7 THEN 1 ELSE 0 END )
```

### 3b. On `daily_stress` — Page 1 rolling 30-day line

```
// Is High Stress — row-level flag
IF [stress_01] > 0.7 THEN 1 ELSE 0 END
```
```
// High Stress Days (30d) — TABLE CALC. "Number of High Stress Days in Previous 30 Days".
// On the line chart, put exact/continuous DAY(date) on Columns and BA on Color, then:
//   Compute Using = date (per BA pane). This sums the flag over the trailing 30 days.
WINDOW_SUM( SUM([Is High Stress]), -29, 0 )
```
> This is the one measure with no direct scalar equivalent — Power BI did it with a
> `CALCULATE(..., DATESINPERIOD(...))` rolling measure. In Tableau it's a windowed
> table calc: set **Compute Using → date**, and make sure the date axis is continuous
> (green) at DAY level so the 30-step window means 30 days.

### 3c. On `daily_stress` — the Daily Stress Calculator (Page 2)

Baseline mean/std hardcoded from `baseline_stats.csv` (constants — a calculator needs
its inputs disconnected from the row data, exactly as Power BI's what-if table was):

```
// Peak Mean
IF [Calc BA] = "CISO" THEN 29561.6932 ELSE 109157.4548 END
```
```
// Peak Std
IF [Calc BA] = "CISO" THEN 4312.5014 ELSE 17697.646 END
```
```
// Ramp Mean
IF [Calc BA] = "CISO" THEN 2383.2767 ELSE 5749.3616 END
```
```
// Ramp Std
IF [Calc BA] = "CISO" THEN 635.3495 ELSE 1360.4761 END
```
```
// Input Z Peak
([Peak MW Input] - [Peak Mean]) / [Peak Std]
```
```
// Input Z Ramp
([Max Ramp MW Input] - [Ramp Mean]) / [Ramp Std]
```
```
// Input Stress Z — KPI card.  Peak 40000 / Ramp 3000 / CISO → 3.39 ✓
[Input Z Peak] + [Input Z Ramp]
```

Nearest-centroid assignment. Centroid coords hardcoded from `cluster_centroids.csv`
(per BA). Define the 8 centroid constants, 4 distances, then the label:

```
// Centroid Z-Peak per cluster (one field each)
cP_Stable   :  IF [Calc BA]="CISO" THEN -0.6457 ELSE -0.8337 END
cP_Moderate :  IF [Calc BA]="CISO" THEN -0.3120 ELSE -0.6521 END
cP_Elevated :  IF [Calc BA]="CISO" THEN  1.0891 ELSE  0.3664 END
cP_Extreme  :  IF [Calc BA]="CISO" THEN  2.0691 ELSE  1.5823 END

// Centroid Z-Ramp per cluster
cR_Stable   :  IF [Calc BA]="CISO" THEN -0.8300 ELSE -1.3496 END
cR_Moderate :  IF [Calc BA]="CISO" THEN  0.4164 ELSE  0.4510 END
cR_Elevated :  IF [Calc BA]="CISO" THEN  0.3345 ELSE -0.0852 END
cR_Extreme  :  IF [Calc BA]="CISO" THEN  2.0651 ELSE  1.1240 END
```
```
// Distances (Euclidean in z-space) — one field each
d_Stable   : SQRT( POWER([Input Z Peak]-[cP_Stable],2)   + POWER([Input Z Ramp]-[cR_Stable],2) )
d_Moderate : SQRT( POWER([Input Z Peak]-[cP_Moderate],2) + POWER([Input Z Ramp]-[cR_Moderate],2) )
d_Elevated : SQRT( POWER([Input Z Peak]-[cP_Elevated],2) + POWER([Input Z Ramp]-[cR_Elevated],2) )
d_Extreme  : SQRT( POWER([Input Z Peak]-[cP_Extreme],2)  + POWER([Input Z Ramp]-[cR_Extreme],2) )
```
```
// Identified Cluster — KPI card.  Peak 40000 / Ramp 3000 / CISO → "Extreme" ✓
IF   [d_Stable]   <= [d_Moderate] AND [d_Stable]   <= [d_Elevated] AND [d_Stable] <= [d_Extreme] THEN "Stable"
ELSEIF [d_Moderate] <= [d_Elevated] AND [d_Moderate] <= [d_Extreme] THEN "Moderate"
ELSEIF [d_Elevated] <= [d_Extreme] THEN "Elevated"
ELSE "Extreme" END
```
```
// Cluster Mean Stress Z — KPI card.  → 4.13 ✓  (mean_stress_z of the identified cluster)
CASE [Identified Cluster]
  WHEN "Stable"   THEN IF [Calc BA]="CISO" THEN -1.4756 ELSE -2.1833 END
  WHEN "Moderate" THEN IF [Calc BA]="CISO" THEN  0.1044 ELSE -0.2011 END
  WHEN "Elevated" THEN IF [Calc BA]="CISO" THEN  1.4236 ELSE  0.2812 END
  WHEN "Extreme"  THEN IF [Calc BA]="CISO" THEN  4.1342 ELSE  2.7064 END
END
```
```
// Stress Percentile — KPI card. Share of the BA's 365 days with stress_z <= Input Stress Z.
//   Peak 40000 / Ramp 3000 / CISO → 343/365 = 94% ✓   Format as Percentage, 0 dp.
{ FIXED [balancing_authority] : SUM(IF [stress_z] <= [Input Stress Z] THEN 1 ELSE 0 END) }
/
{ FIXED [balancing_authority] : COUNT([date]) }
```

> **Calculator worksheet setup:** build all 4 calculator cards on the `daily_stress`
> source with a filter `[balancing_authority] = [Calc BA]` (create that boolean calc and
> set it to True) so each card resolves to a single BA. Drop the measure on Text, use
> `MIN`/`ATTR` to collapse to one number (the values are constant per BA anyway).

### 3d. On `page3_data` — record_type filters

No calc needed; each visual filters `record_type` to the right slice (see §5–6). Keep
`mean_z_peak`, `mean_z_ramp`, `mean_stress_z`, `mean_onset_days`, `n_days`,
`silhouette_score` as measures; `relative_day` as continuous dimension.

---

## 4. Page 1 — "Electric Grid Stress Analysis · Overview"

| Worksheet | Type | Shelves |
|---|---|---|
| **Daily Stress_01** | Line | Columns: `DAY(date)` (continuous). Rows: `SUM(stress_01)`. Color: `balancing_authority` (CISO light blue, PJM dark blue). |
| **Avg Stress by Month** | Combo (dual axis) | Columns: `MONTH(date)`. Bars: `AVG(z_daily_max_ramp_mw)` + `AVG(z_daily_peak_mw)` via Measure Names on Color, stacked. Line (2nd axis, synchronized): `AVG(stress_z)` in orange. Rename measures on the legend to **Z (Max Ramp)** / **Z (Peak)** / **Total Stress_Z**. |
| **High Stress Days 30d** | Line | Columns: `DAY(date)` continuous. Rows: `High Stress Days (30d)` (Compute Using → date). Color: `balancing_authority`. |
| **Most Stressful Days** | Text table | Rows: `balancing_authority`, `date`. Text: `stress_01`. Sort ascending by `stress_01` (matches the PBI table). Data source = `top_days`. |
| **KPI: Stress_Z (Max)** | Text (BA on Rows) | Text: `Stress_Z (Max)`. |
| **KPI: Stress_01 (Avg)** | Text (BA on Rows) | Text: `Stress_01 (Avg)`. |
| **KPI: Most Stressed Day** | Text (BA on Rows) | Text: `Most Stressed Day` (format mmm dd). |
| **KPI: High Stress Days** | Text (BA on Rows) | Text: `High Stress Days`. |

BA slicer → add `balancing_authority` as a filter, "Show Filter", single-value list
(add "Select all" via the (All) option). Text boxes for the "Analytic Structure" panel
and the annotations reproduce verbatim from the p1 render.

---

## 5. Page 2 — "ML Clustering"

| Worksheet | Type | Shelves / notes |
|---|---|---|
| **Z-Score Clustering** | Scatter | Columns: `z_daily_peak_mw`, Rows: `z_daily_max_ramp_mw`. **Analysis > Aggregate Measures = OFF** (one mark per day), or put `date` on Detail. Color: `cluster_label` (Stable purple, Moderate orange, Elevated light-blue, Extreme dark-blue). Filter BA = `[Calc BA]`. |
| **Frequency by Cluster** | Donut | `COUNT(date)` by `cluster_label`. Standard donut = dual-axis of two synced `MIN(0)`… or use a Pie mark + white circle overlay. Show % of total labels. |
| **Average Z-Scores by Cluster** | Horizontal bars | Rows: `cluster_label`. Columns: Measure Values = `AVG(z_daily_max_ramp_mw)`, `AVG(z_daily_peak_mw)`, `AVG(stress_z)`; Measure Names on Color. |
| **Days by Cluster & Season** | Stacked bars | Source `page3_data`, filter `record_type = "composition"` + BA. Columns: `cluster_label`. Rows: `SUM(n_days)`. Color: `season` (Shoulder light-blue, Summer dark-blue, Winter orange). Label with `n_days`. |
| **Silhouette Scores** | Text table | Source `k_selection`. Rows: `k`. Columns: `balancing_authority`. Text: `SUM(silhouette)`. Turn on `Analysis > Totals > Row/Column Grand Totals` for the CISO+PJM "Total" column and the bottom Total row. Bold `selected = Yes` (k=4). |
| **Calc: Identified Cluster** | Text card | `Identified Cluster` on Text (filter `[balancing_authority]=[Calc BA]`). |
| **Calc: Input Stress Z** | Text card | `ATTR/MIN(Input Stress Z)`. |
| **Calc: Stress Percentile** | Text card | `MIN(Stress Percentile)`, format %. |
| **Calc: Cluster Mean Stress Z** | Text card | `ATTR/MIN(Cluster Mean Stress Z)`. |

Calculator input controls: show `Peak MW Input`, `Max Ramp MW Input`, `Calc BA`
parameter controls on the dashboard. Text boxes for the "Approximate 2025 Ranges" and
"Model Validation" annotations.

---

## 6. Page 3 — "Event Drilldown"

All three composite line charts share one worksheet template off `page3_data`,
`record_type = "composite"`, duplicated 3× with different BA/season filters:

| Worksheet | Filter | Shelves |
|---|---|---|
| **Composite — CAISO Summer** | BA=CISO, season=Summer | Columns: `relative_day` (continuous). Rows: `mean_stress_z`, `mean_z_peak`, `mean_z_ramp` (Measure Names on Color → Mean Stress Z / Mean Z Peak / Mean Z Ramp). |
| **Composite — PJM Summer** | BA=PJM, season=Summer | same |
| **Composite — PJM Winter** | BA=PJM, season=Winter | same |
| **Lead Days to Extreme Event** | `record_type = "onset"` | Rows: `balancing_authority`, `season`. Columns: `mean_onset_days` (rename axis "Lead Days"). Color: `component` (Max Ramp / Peak Load). Horizontal bars. |
| **Hourly Demand on Extreme Day** | source `hourly_peak_days`, `metric IN (demand_mw, net_load_mw)`, BA+season slicers | Columns: `hour`. Rows: `SUM(value)`. Color: `metric`. |
| **Hourly Ramp on Extreme Day** | `hourly_peak_days`, `metric = ramp_mw` | Columns: `hour`. Rows: `SUM(value)`. Orange line. |

BA slicer (`balancing_authority`) + season slicer (`season`) drive the hourly charts —
add both as "Show Filter" controls. `hourly_peak_days` also has `solar_mw` available if
you want to extend the hourly view later.

---

## 7. Dashboard assembly

Build 3 dashboards (one per page), each **1600 × 900** fixed size to match the PBI
canvas. Layout mirrors the p1/p2/p3 renders:

- **Overview:** top row = Daily Stress_01 | Avg Stress by Month | Analytic Structure text + BA slicer. Mid-right = Most Stressful Days table. Bottom-left = High Stress Days 30d line. Bottom-right = the 4 KPI cards (each with CISO/PJM rows) + threshold note.
- **ML Clustering:** left column = scatter + avg-z bars. Middle = donut + season-composition bars + silhouette table. Right = BA control + the Daily Stress Calculator (2×2 KPI grid) + range/validation notes.
- **Event Drilldown:** top row = 3 composite line charts. Bottom-left = Lead Days bars. Middle = Hourly Demand + Hourly Ramp with BA/season slicers. Right = Summary notes text.

**Cross-filtering:** add a dashboard filter action on `balancing_authority` (Page 1),
and use the `Calc BA` parameter + a filter action on Page 2 so the BA selection drives
both the calculator and the other visuals — the Tableau-native equivalent of the PBI
single-select slicers.

### Color reference (match PBI)
- BA: **CISO** `#3AA0FF` (light blue), **PJM** `#12239E` (dark blue)
- Clusters: **Stable** `#7A2E8E` purple · **Moderate** `#E8703A` orange · **Elevated** `#3AA0FF` light blue · **Extreme** `#12239E` dark blue
- Total Stress_Z line: `#E8703A` orange

---

## 8. Validation checklist (confirm the port matches)

With default calculator inputs (CISO, Peak 40000, Ramp 3000):

- [ ] Input Stress Z = **3.39**
- [ ] Identified Cluster = **Extreme**
- [ ] Cluster Mean Stress Z = **4.13**
- [ ] Stress Percentile = **94%**
- [ ] KPI cards: CISO Max Stress_Z 6.60 / Avg 0.31 / Sep 03 / 18 high days; PJM 4.83 / 0.43 / Jun 24 / 46
- [ ] Donut (CISO): Stable 44% / Moderate 30% / Elevated 18% / Extreme 9%
- [ ] Silhouette: k=4 selected for both BAs; CISO total 2.06, PJM 2.04
