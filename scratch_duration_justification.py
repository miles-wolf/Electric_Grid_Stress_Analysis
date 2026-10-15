"""
One-off analysis: compare duration metric candidates side by side.

For each candidate, reports:
  - Pearson r with daily_peak_mw       (redundancy with raw peak)
  - Pearson r with z_daily_peak_mw     (redundancy with z-scored peak)
  - Pearson r with base_fragility_z    (= z_peak + z_ramp, no duration term)

This justifies the two-component index decision in the report.
"""

import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

HOURLY_PARQUET  = Path("data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet")
DAILY_PARQUET   = Path("data/processed/stress/daily_stress_pjm_ciso_2025.parquet")
COL_BA          = "balancing_authority"
COL_TS          = "timestamp_utc"
COL_DEMAND      = "demand_(mw)_(adjusted)"

# ── 1. Load data ─────────────────────────────────────────────────────────────

hourly = pd.read_parquet(HOURLY_PARQUET)
hourly[COL_TS] = pd.to_datetime(hourly[COL_TS])
hourly = hourly.sort_values([COL_BA, COL_TS]).dropna(subset=[COL_DEMAND])
hourly["date"] = hourly[COL_TS].dt.date

daily = pd.read_parquet(DAILY_PARQUET)
daily["date"] = pd.to_datetime(daily["date"]).dt.date

# ── 2. Compute duration candidates from hourly data ───────────────────────────

# Candidate A: pct_hours_near_peak at 95% of daily peak (original)
daily_peak = (
    hourly.groupby([COL_BA, "date"])[COL_DEMAND]
    .max()
    .reset_index(name="daily_peak_mw_h")
)
hourly = hourly.merge(daily_peak, on=[COL_BA, "date"], how="left")
hourly["near_peak_95"] = hourly[COL_DEMAND] >= 0.95 * hourly["daily_peak_mw_h"]
hourly["near_peak_85"] = hourly[COL_DEMAND] >= 0.85 * hourly["daily_peak_mw_h"]

cand_a = (
    hourly.groupby([COL_BA, "date"])["near_peak_95"]
    .mean()
    .reset_index(name="pct_near_peak_95")
)

cand_a2 = (
    hourly.groupby([COL_BA, "date"])["near_peak_85"]
    .mean()
    .reset_index(name="pct_near_peak_85")
)

# Candidate B: pct_hours_above_annual_p90
p90 = hourly.groupby(COL_BA)[COL_DEMAND].transform(lambda x: x.quantile(0.90))
hourly["above_p90"] = hourly[COL_DEMAND] >= p90
cand_b = (
    hourly.groupby([COL_BA, "date"])["above_p90"]
    .mean()
    .reset_index(name="pct_above_annual_p90")
)

# Candidate C: pct_hours_above_annual_p75
p75 = hourly.groupby(COL_BA)[COL_DEMAND].transform(lambda x: x.quantile(0.75))
hourly["above_p75"] = hourly[COL_DEMAND] >= p75
cand_c = (
    hourly.groupby([COL_BA, "date"])["above_p75"]
    .mean()
    .reset_index(name="pct_above_annual_p75")
)

# Merge candidates onto daily
df = daily.merge(cand_a,  on=[COL_BA, "date"], how="left")
df = df.merge(cand_a2, on=[COL_BA, "date"], how="left")
df = df.merge(cand_b,  on=[COL_BA, "date"], how="left")
df = df.merge(cand_c,  on=[COL_BA, "date"], how="left")

# ── 3. Z-score each candidate within BA ───────────────────────────────────────

def zscore_within_ba(df, col):
    return df.groupby(COL_BA)[col].transform(
        lambda x: (x - x.mean()) / (x.std(ddof=0) if x.std(ddof=0) != 0 else np.nan)
    )

df["z_near_peak_95"]       = zscore_within_ba(df, "pct_near_peak_95")
df["z_near_peak_85"]       = zscore_within_ba(df, "pct_near_peak_85")
df["z_above_annual_p90"]   = zscore_within_ba(df, "pct_above_annual_p90")
df["z_above_annual_p75"]   = zscore_within_ba(df, "pct_above_annual_p75")

# Candidate D: z_star = z_near_peak_95 * max(0, z_peak)  (smooth multiplier)
df["z_star"] = df["z_near_peak_95"] * df["z_daily_peak_mw"].clip(lower=0)

# ── 4. Two-component base fragility (no duration term) ────────────────────────

df["base_fragility_z"] = df["z_daily_peak_mw"] + df["z_daily_max_ramp_mw"]

# ── 5. Correlation table ──────────────────────────────────────────────────────

candidates = {
    "pct_near_peak_95 (original 95%)":  "z_near_peak_95",
    "pct_near_peak_85 (85% threshold)": "z_near_peak_85",
    "pct_above_annual_p90":             "z_above_annual_p90",
    "pct_above_annual_p75":             "z_above_annual_p75",
    "z_star (smooth multiplier)":       "z_star",
}

ref_cols = {
    "r w/ daily_peak_mw":    "daily_peak_mw",
    "r w/ z_peak":           "z_daily_peak_mw",
    "r w/ base_fragility_z": "base_fragility_z",
}

print("\n" + "=" * 72)
print("DURATION METRIC CORRELATION COMPARISON")
print("base_fragility_z = z_peak + z_ramp  (no duration term)")
print("=" * 72)

for ba, grp in df.groupby(COL_BA):
    display = "CAISO" if ba == "CISO" else ba
    print(f"\n-- {display} --------------------------------------------------")
    header = f"{'Metric':<38}" + "".join(f"{h:>22}" for h in ref_cols)
    print(header)
    print("-" * 72)
    for label, col in candidates.items():
        row = f"{label:<38}"
        for ref_label, ref_col in ref_cols.items():
            r, _ = stats.pearsonr(grp[col].dropna(), grp[ref_col].loc[grp[col].dropna().index])
            row += f"{r:>22.3f}"
        print(row)

print("\n" + "=" * 72)
print("COMBINED (both BAs)")
print("=" * 72)
header = f"{'Metric':<38}" + "".join(f"{h:>22}" for h in ref_cols)
print(header)
print("-" * 72)
for label, col in candidates.items():
    row = f"{label:<38}"
    sub = df.dropna(subset=[col])
    for ref_label, ref_col in ref_cols.items():
        r, _ = stats.pearsonr(sub[col], sub[ref_col])
        row += f"{r:>22.3f}"
    print(row)
