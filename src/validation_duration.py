"""
Duration Metric Justification — Electric Grid Demand Stress Analysis

Evaluates five candidate duration metrics against the two-component stress
index (stress_z = z_peak + z_ramp) to justify why no duration term was added.

For each candidate, reports Pearson r with:
  - daily_peak_mw   (redundancy with raw peak load)
  - z_daily_peak_mw (redundancy with standardised peak)
  - stress_z        (directionality relative to the final index)

A valid duration term must be both:
  (a) positively correlated with stress_z  (same direction as other components)
  (b) not near-perfectly correlated with z_daily_peak_mw  (not redundant)

All five candidates fail at least one criterion. This table is the evidence.

Output: reports/figures/validation/duration_metric_justification.csv
"""

import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

HOURLY_PARQUET = Path("data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet")
DAILY_PARQUET  = Path("data/processed/stress/daily_stress_pjm_ciso_2025.parquet")
OUT_CSV        = Path("reports/figures/validation/duration_metric_justification.csv")

COL_BA     = "balancing_authority"
COL_TS     = "timestamp_utc"
COL_DEMAND = "demand_(mw)_(adjusted)"

CANDIDATES = {
    "% hours >= 95% of daily peak":    "z_near_peak_95",
    "% hours >= 85% of daily peak":    "z_near_peak_85",
    "% hours above annual P90":        "z_above_annual_p90",
    "% hours above annual P75":        "z_above_annual_p75",
    "Smooth multiplier (z* = z_pct x max(0, z_peak))": "z_star",
}

REFERENCE_COLS = {
    "r_daily_peak_mw": "daily_peak_mw",
    "r_z_peak":        "z_daily_peak_mw",
    "r_stress_z":      "stress_z",
}


def build_dataset() -> pd.DataFrame:
    hourly = pd.read_parquet(HOURLY_PARQUET)
    hourly[COL_TS] = pd.to_datetime(hourly[COL_TS])
    hourly = hourly.sort_values([COL_BA, COL_TS]).dropna(subset=[COL_DEMAND])
    hourly["date"] = hourly[COL_TS].dt.date

    daily = pd.read_parquet(DAILY_PARQUET)
    daily["date"] = pd.to_datetime(daily["date"]).dt.date

    # Relative-to-daily-peak candidates
    daily_peak = (
        hourly.groupby([COL_BA, "date"])[COL_DEMAND]
        .max()
        .reset_index(name="daily_peak_mw_h")
    )
    hourly = hourly.merge(daily_peak, on=[COL_BA, "date"], how="left")
    hourly["near_peak_95"] = hourly[COL_DEMAND] >= 0.95 * hourly["daily_peak_mw_h"]
    hourly["near_peak_85"] = hourly[COL_DEMAND] >= 0.85 * hourly["daily_peak_mw_h"]

    cand_95 = hourly.groupby([COL_BA, "date"])["near_peak_95"].mean().reset_index(name="pct_near_peak_95")
    cand_85 = hourly.groupby([COL_BA, "date"])["near_peak_85"].mean().reset_index(name="pct_near_peak_85")

    # Annual-percentile candidates
    p90 = hourly.groupby(COL_BA)[COL_DEMAND].transform(lambda x: x.quantile(0.90))
    hourly["above_p90"] = hourly[COL_DEMAND] >= p90
    cand_p90 = hourly.groupby([COL_BA, "date"])["above_p90"].mean().reset_index(name="pct_above_annual_p90")

    p75 = hourly.groupby(COL_BA)[COL_DEMAND].transform(lambda x: x.quantile(0.75))
    hourly["above_p75"] = hourly[COL_DEMAND] >= p75
    cand_p75 = hourly.groupby([COL_BA, "date"])["above_p75"].mean().reset_index(name="pct_above_annual_p75")

    df = daily.merge(cand_95,  on=[COL_BA, "date"], how="left")
    df = df.merge(cand_85,  on=[COL_BA, "date"], how="left")
    df = df.merge(cand_p90, on=[COL_BA, "date"], how="left")
    df = df.merge(cand_p75, on=[COL_BA, "date"], how="left")

    def zscore_within_ba(col):
        return df.groupby(COL_BA)[col].transform(
            lambda x: (x - x.mean()) / (x.std(ddof=0) if x.std(ddof=0) != 0 else np.nan)
        )

    df["z_near_peak_95"]     = zscore_within_ba("pct_near_peak_95")
    df["z_near_peak_85"]     = zscore_within_ba("pct_near_peak_85")
    df["z_above_annual_p90"] = zscore_within_ba("pct_above_annual_p90")
    df["z_above_annual_p75"] = zscore_within_ba("pct_above_annual_p75")
    df["z_star"]             = df["z_near_peak_95"] * df["z_daily_peak_mw"].clip(lower=0)

    return df


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    groups = [(ba, grp) for ba, grp in df.groupby(COL_BA)]
    groups.append(("Combined", df))

    for ba, grp in groups:
        display = "CAISO" if ba == "CISO" else ba
        for label, cand_col in CANDIDATES.items():
            valid = grp.dropna(subset=[cand_col])
            row = {"ba": display, "duration_metric": label}
            for out_col, ref_col in REFERENCE_COLS.items():
                r, _ = stats.pearsonr(valid[cand_col], valid[ref_col])
                row[out_col] = round(r, 3)
            rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    print("Building dataset...")
    df = build_dataset()

    print("Computing correlations...")
    table = compute_correlations(df)

    table.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}")

    # Pretty-print to console
    for ba, grp in table.groupby("ba", sort=False):
        print(f"\n{'='*68}")
        print(f"  {ba}")
        print(f"{'='*68}")
        print(f"  {'Metric':<45} {'r_peak_mw':>10} {'r_z_peak':>10} {'r_stress_z':>11}")
        print(f"  {'-'*45} {'-'*10} {'-'*10} {'-'*11}")
        for _, r in grp.iterrows():
            print(f"  {r['duration_metric']:<45} {r['r_daily_peak_mw']:>10.3f} {r['r_z_peak']:>10.3f} {r['r_stress_z']:>11.3f}")


if __name__ == "__main__":
    main()
