from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from src.feature_utils import add_size_normalized_features, add_rolling_zscores, repair_demand_spikes




def pick_demand_series(df: pd.DataFrame) -> pd.Series:
    """
    Prefer adjusted demand if present, else raw demand.
    This returns a Series aligned to df.
    """
    adj_candidates = [
        "demand_(mw)_(adjusted)",
        "demand_mw_adjusted",
        "demand_mw_adj",
    ]
    raw_candidates = [
        "demand_(mw)",
        "demand_mw",
        "demand",
    ]

    for c in adj_candidates:
        if c in df.columns:
            return df[c]
    for c in raw_candidates:
        if c in df.columns:
            return df[c]

    raise ValueError(
        "Could not find a demand column. Looked for adjusted + raw candidates."
    )


def robust_quantile(x: np.ndarray, q: float) -> float:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.nan
    return float(np.quantile(x, q))


def daily_features_for_group(g: pd.DataFrame) -> dict:
    """
    g is one BA-day slice with hourly rows.
    Must contain columns: demand_mw (cleaned), ramp_mw.
    """
    x = g["demand_mw"].to_numpy(dtype=float)
    r = g["ramp_mw"].to_numpy(dtype=float)

    n_hours = int(np.isfinite(x).sum())
    n_missing = int(np.isnan(x).sum())
    coverage = n_hours / 24.0

    # Demand stats
    demand_mean = float(np.nanmean(x)) if n_hours else np.nan
    demand_std = float(np.nanstd(x, ddof=0)) if n_hours else np.nan
    demand_min = float(np.nanmin(x)) if n_hours else np.nan
    demand_max = float(np.nanmax(x)) if n_hours else np.nan
    intra_range = demand_max - demand_min if np.isfinite(demand_max) and np.isfinite(demand_min) else np.nan
    demand_cv = (demand_std / demand_mean) if (np.isfinite(demand_std) and np.isfinite(demand_mean) and demand_mean != 0) else np.nan

    # Peak / concentration
    peak_to_mean = (demand_max / demand_mean) if (np.isfinite(demand_max) and np.isfinite(demand_mean) and demand_mean != 0) else np.nan

    # Top-4 hours mean
    x_f = x[np.isfinite(x)]
    if x_f.size >= 4:
        top4_mean = float(np.mean(np.sort(x_f)[-4:]))
    elif x_f.size > 0:
        top4_mean = float(np.mean(x_f))
    else:
        top4_mean = np.nan

    top4_to_mean = (top4_mean / demand_mean) if (np.isfinite(top4_mean) and np.isfinite(demand_mean) and demand_mean != 0) else np.nan

    # Peak hour (UTC hour)
    if x_f.size > 0:
        # use idxmax on the group to keep hour label
        peak_row = g.loc[g["demand_mw"].idxmax()]
        peak_hour = int(peak_row["hour_utc"])
    else:
        peak_hour = np.nan

    # Duration near peak: count above daily P90
    p90 = robust_quantile(x, 0.90)
    hours_above_p90 = int(np.sum(x >= p90)) if np.isfinite(p90) else 0

    # Ramp stats (note: first hour ramp is NaN because diff)
    r_f = r[np.isfinite(r)]
    if r_f.size > 0:
        max_up = float(np.max(r_f))
        max_down = float(np.min(r_f))
        max_abs = float(np.max(np.abs(r_f)))
        ramp_std = float(np.std(r_f, ddof=0))
        mean_abs = float(np.mean(np.abs(r_f)))
        p95_abs = robust_quantile(np.abs(r_f), 0.95)

        # “Ramp events” above a robust daily threshold (median + 3*MAD)
        med = float(np.median(r_f))
        mad = float(np.median(np.abs(r_f - med)))
        thr = abs(med) + 3.0 * mad  # simple, robust
        ramp_events_gt_thr = int(np.sum(np.abs(r_f) > thr)) if np.isfinite(thr) else 0
    else:
        max_up = max_down = max_abs = ramp_std = mean_abs = p95_abs = np.nan
        ramp_events_gt_thr = 0

    return {
        # integrity
        "n_hours": n_hours,
        "n_missing": n_missing,
        "coverage": coverage,

        # demand shape
        "demand_mean_mw": demand_mean,
        "demand_std_mw": demand_std,
        "demand_cv": demand_cv,
        "demand_min_mw": demand_min,
        "demand_peak_mw": demand_max,
        "intra_day_range_mw": intra_range,

        # peak stress
        "peak_to_mean": peak_to_mean,
        "top4_mean_mw": top4_mean,
        "top4_to_mean": top4_to_mean,
        "peak_hour_utc": peak_hour,
        "hours_above_p90": hours_above_p90,

        # ramp stress
        "max_up_ramp_mw": max_up,
        "max_down_ramp_mw": max_down,
        "max_abs_ramp_mw": max_abs,
        "ramp_std_mw": ramp_std,
        "mean_abs_ramp_mw": mean_abs,
        "ramp_p95_abs_mw": p95_abs,
        "ramp_events_gt_robust_thr": ramp_events_gt_thr,
    }


def main(in_path: Path, out_path: Path) -> None:
    df = pd.read_parquet(in_path)

    # --- expected columns / light normalization ---
    # You likely have: timestamp_utc, BA label (maybe "ba" or "balancing_authority")
    # We'll try common names:
    ba_col_candidates = ["ba", "BA", "balancing_authority", "ba_code", "respondent"]
    ba_col = next((c for c in ba_col_candidates if c in df.columns), None)
    if ba_col is None:
        raise ValueError(f"Could not find BA column. Tried: {ba_col_candidates}")

    ts_col_candidates = ["timestamp_utc", "utc_time_at_end_of_hour", "timestamp"]
    ts_col = next((c for c in ts_col_candidates if c in df.columns), None)
    if ts_col is None:
        raise ValueError(f"Could not find timestamp column. Tried: {ts_col_candidates}")

    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)

    # Select demand series
    df["demand_mw"] = pick_demand_series(df).astype(float)

    # Derive day/hour (UTC)
    df["date_utc"] = df[ts_col].dt.floor("D")

    df["hour_utc"] = df[ts_col].dt.hour

    # Sort so diff works correctly per BA
    df = df.sort_values([ba_col, ts_col])

    # Repair isolated single-hour demand spikes before computing ramps
    df = repair_demand_spikes(df, ba_col=ba_col, ts_col=ts_col, demand_col="demand_mw")

    # Hourly ramp per BA
    df["ramp_mw"] = df.groupby(ba_col)["demand_mw"].diff()

    # Build daily features per BA-date
    feature_rows = []
    for (ba, date), g in df.groupby([ba_col, "date_utc"], sort=True):
        feats = daily_features_for_group(g)
        feats[ba_col] = ba
        feats["date_utc"] = date
        feature_rows.append(feats)

    out = pd.DataFrame(feature_rows).sort_values([ba_col, "date_utc"])

    # ---- extensions (now modular functions) ----
    out = add_size_normalized_features(out)

    out = add_rolling_zscores(
        df=out,
        group_col=ba_col,
        time_col="date_utc",
        cols=["max_abs_ramp_mw", "peak_to_mean", "demand_cv"],
        window=7,
    )
    # -------------------------------------------


    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to parquet
    out.to_parquet(out_path, index=False)
    
    # Save to CSV
    csv_path = out_path.with_suffix('.csv')
    out.to_csv(csv_path, index=False)
    
    # Save to JSON
    json_path = out_path.with_suffix('.json')
    out.to_json(json_path, orient='records', date_format='iso', indent=2)

    # Quick summary print
    print(f"INPUT : {in_path}")
    print(f"OUTPUT (Parquet): {out_path}")
    print(f"OUTPUT (CSV)    : {csv_path}")
    print(f"OUTPUT (JSON)   : {json_path}")
    print("rows:", len(out))
    print("BAs:", sorted(out[ba_col].unique().tolist()))
    print("min date_utc:", out["date_utc"].min())
    print("max date_utc:", out["date_utc"].max())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True)
    p.add_argument("--out", dest="out_path", required=True)
    args = p.parse_args()
    main(Path(args.in_path), Path(args.out_path))
