"""
Module 3 — Daily Demand Stress Score + Plots

Reads hourly EIA-930 processed parquet (Module 1/2 output),
engineers daily features, computes two demand stress indices:
- stress_z  (z-score composite, per BA)
- stress_01 (0-1 scaled version of stress_z, per BA)

Outputs:
- data/processed/stress/daily_stress_pjm_ciso_2025.parquet
- reports/figures/stress_daily/stress_timeseries.png
- reports/figures/stress_daily/stress_distribution.png
- reports/figures/stress_daily/top_days_table.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.feature_utils import repair_demand_spikes as _repair_demand_spikes


# -----------------------------
# CONFIG: update paths here only
# -----------------------------
INPUT_PARQUET = Path("data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet")
OUTPUT_PARQUET = Path("data/processed/stress/daily_stress_pjm_ciso_2025.parquet")

FIG_DIR = Path("reports/figures/stress_daily")
TOP_DAYS_CSV = FIG_DIR / "top_days_table.csv"

# Core columns expected from Module 1/2 output
COL_BA = "balancing_authority"
COL_TS = "timestamp_utc"
COL_DEMAND = "demand_(mw)_(adjusted)"

TOP_N_DAYS = 10

ANALYSIS_YEAR = 2025

SEASON_MAP = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Shoulder", 4: "Shoulder", 5: "Shoulder",
    6: "Summer", 7: "Summer", 8: "Summer", 9: "Summer",
    10: "Shoulder", 11: "Shoulder",
}

def ensure_dirs() -> None:
    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_hourly() -> pd.DataFrame:
    if not INPUT_PARQUET.exists():
        raise FileNotFoundError(
            f"Could not find input parquet at: {INPUT_PARQUET}\n"
            f"Confirm Module 1 created it, or update INPUT_PARQUET in this script."
        )

    df = pd.read_parquet(INPUT_PARQUET)

    missing = [c for c in [COL_BA, COL_TS, COL_DEMAND] if c not in df.columns]
    if missing:
        raise ValueError(
            f"Input is missing expected columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )

    df[COL_TS] = pd.to_datetime(df[COL_TS], errors="coerce")
    if df[COL_TS].isna().any():
        bad = df[df[COL_TS].isna()].head(5)
        raise ValueError(
            "Some timestamps could not be parsed into datetime. Example rows:\n"
            f"{bad[[COL_BA, COL_TS, COL_DEMAND]]}"
        )

    df = df.sort_values([COL_BA, COL_TS]).reset_index(drop=True)
    df = df.dropna(subset=[COL_DEMAND]).copy()

    return df


def repair_demand_spikes(df: pd.DataFrame) -> pd.DataFrame:
    return _repair_demand_spikes(df, ba_col=COL_BA, ts_col=COL_TS, demand_col=COL_DEMAND)


def engineer_daily_features(df: pd.DataFrame) -> pd.DataFrame:
    df["hourly_ramp_mw"] = df.groupby(COL_BA)[COL_DEMAND].diff()

    df["date"] = df[COL_TS].dt.date

    daily = (
        df.groupby([COL_BA, "date"])
        .agg(
            daily_peak_mw=(COL_DEMAND, "max"),
            daily_min_mw=(COL_DEMAND, "min"),
            daily_max_ramp_mw=("hourly_ramp_mw", lambda x: np.nanmax(np.abs(x.values))),
            daily_ramp_std=("hourly_ramp_mw", "std"),
            daily_energy_mwh=(COL_DEMAND, "sum"),
            hours_observed=(COL_DEMAND, "size"),
        )
        .reset_index()
    )

    daily["daily_range_mw"] = daily["daily_peak_mw"] - daily["daily_min_mw"]

    return daily


def add_season_and_filter_year(daily: pd.DataFrame, year: int = ANALYSIS_YEAR) -> pd.DataFrame:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["season"] = daily["date"].dt.month.map(SEASON_MAP)
    before = len(daily)
    daily = daily[daily["date"].dt.year == year].reset_index(drop=True)
    dropped = before - len(daily)
    if dropped:
        print(f"Dropped {dropped} row(s) outside year {year} (raw EIA timezone spillover)")
    return daily


def add_stress_scores(daily: pd.DataFrame) -> pd.DataFrame:
    feat_cols = ["daily_peak_mw", "daily_max_ramp_mw"]

    for col in feat_cols:
        zcol = f"z_{col}"
        daily[zcol] = (
            daily.groupby(COL_BA)[col]
            .transform(
                lambda x: (x - x.mean())
                / (x.std(ddof=0) if x.std(ddof=0) != 0 else np.nan)
            )
        )

    # Composite demand stress index (two-component)
    daily["stress_z"] = daily["z_daily_peak_mw"] + daily["z_daily_max_ramp_mw"]

    # 0-1 scaled stress (per BA)
    def minmax(s: pd.Series) -> pd.Series:
        smin, smax = s.min(), s.max()
        if pd.isna(smin) or pd.isna(smax) or smax == smin:
            return pd.Series(np.nan, index=s.index)
        return (s - smin) / (smax - smin)

    daily["stress_01"] = daily.groupby(COL_BA)["stress_z"].transform(minmax)

    return daily


def save_outputs(daily: pd.DataFrame) -> None:
    daily.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"Wrote daily stress parquet: {OUTPUT_PARQUET}")

    csv_path = OUTPUT_PARQUET.with_suffix('.csv')
    daily.to_csv(csv_path, index=False)
    print(f"Wrote daily stress CSV: {csv_path}")

    json_path = OUTPUT_PARQUET.with_suffix('.json')
    daily.to_json(json_path, orient='records', date_format='iso', indent=2)
    print(f"Wrote daily stress JSON: {json_path}")


def plot_timeseries(daily: pd.DataFrame) -> None:
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    bas = sorted(d[COL_BA].unique())

    fig, ax = plt.subplots(figsize=(12, 5))

    for ba in bas:
        sub = d[d[COL_BA] == ba].sort_values("date")
        ba_label = "CAISO" if ba == "CISO" else ba
        ax.plot(sub["date"], sub["stress_01"], label=ba_label)

    ax.set_ylabel("Demand Stress (0-1)", fontsize=16)
    ax.set_xlabel("Date", fontsize=16)
    ax.legend(loc="upper right")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    plt.tight_layout()

    out = FIG_DIR / "stress_timeseries_stacked.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Wrote plot: {out}")

    # Appendix: three-panel — unfiltered, z-score composite, filtered (0-1)
    raw = load_hourly()
    daily_raw = engineer_daily_features(raw)
    daily_raw = add_season_and_filter_year(daily_raw)
    daily_raw = add_stress_scores(daily_raw)
    daily_raw["date"] = pd.to_datetime(daily_raw["date"])

    fig, (ax_raw, ax_z, ax_01) = plt.subplots(3, 1, figsize=(12, 13), sharex=True)

    for ba in bas:
        ba_label = "CAISO" if ba == "CISO" else ba
        sub_raw = daily_raw[daily_raw[COL_BA] == ba].sort_values("date")
        sub = d[d[COL_BA] == ba].sort_values("date")
        ax_raw.plot(sub_raw["date"], sub_raw["stress_01"], label=ba_label)
        ax_z.plot(sub["date"], sub["stress_z"], label=ba_label)
        ax_01.plot(sub["date"], sub["stress_01"], label=ba_label)

    ax_raw.set_title("Unfiltered (min-max scaled)")
    ax_raw.set_ylabel("Demand Stress (0-1)", fontsize=16)
    ax_raw.legend(loc="upper right")
    ax_raw.grid(alpha=0.3)

    ax_z.set_title("Filtered (z-score composite)")
    ax_z.set_ylabel("Demand Stress (z-score)", fontsize=16)
    ax_z.axhline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax_z.legend(loc="upper right")
    ax_z.grid(alpha=0.3)

    ax_01.set_title("Filtered (min-max scaled)")
    ax_01.set_ylabel("Demand Stress (0-1)", fontsize=16)
    ax_01.set_xlabel("Date", fontsize=16)
    ax_01.legend(loc="upper right")
    ax_01.grid(alpha=0.3)

    ax_01.xaxis.set_major_formatter(mdates.DateFormatter("%m-%Y"))
    plt.setp(ax_01.xaxis.get_majorticklabels(), rotation=45, ha="right")

    plt.tight_layout()

    out_appendix = FIG_DIR / "stress_timeseries_appendix.png"
    plt.savefig(out_appendix, dpi=200)
    plt.close()
    print(f"Wrote plot: {out_appendix}")


def plot_distribution(daily: pd.DataFrame) -> None:
    bas = sorted(daily[COL_BA].unique())

    plt.figure(figsize=(10, 5))
    for ba in bas:
        sub = daily[daily[COL_BA] == ba]["stress_z"].dropna()
        plt.hist(sub, bins=40, alpha=0.5, label=ba)
    plt.xlabel("Demand Stress (z-score)", fontsize=16)
    plt.ylabel("Count of Days", fontsize=16)
    plt.legend()
    plt.tight_layout()

    out = FIG_DIR / "stress_distribution.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Wrote plot: {out}")


def export_top_days(daily: pd.DataFrame) -> None:
    top_rows = []
    for ba, sub in daily.groupby(COL_BA):
        sub = sub.sort_values("stress_z", ascending=False).head(TOP_N_DAYS).copy()
        sub["rank"] = np.arange(1, len(sub) + 1)
        top_rows.append(sub)

    top = pd.concat(top_rows, ignore_index=True)

    keep = [
        COL_BA,
        "rank",
        "date",
        "stress_z",
        "stress_01",
        "daily_peak_mw",
        "daily_max_ramp_mw",
        "daily_range_mw",
        "daily_ramp_std",
        "hours_observed",
    ]
    keep = [c for c in keep if c in top.columns]
    top = top[keep]

    top.to_csv(TOP_DAYS_CSV, index=False)
    print(f"Wrote top stress days table: {TOP_DAYS_CSV}")


def print_sanity_summary(daily: pd.DataFrame) -> None:
    print("\n=== SANITY SUMMARY ===")
    print("Rows (BA-days):", len(daily))
    print("BAs:", sorted(daily[COL_BA].unique()))

    desc = daily.groupby(COL_BA)[["stress_z", "stress_01"]].describe()
    print("\nDemand stress stats by BA:")
    print(desc)

    bad01 = daily[(daily["stress_01"] < -1e-9) | (daily["stress_01"] > 1 + 1e-9)]
    if len(bad01) > 0:
        print("\nWARNING: stress_01 outside [0,1] for some rows (should not happen).")
        print(bad01[[COL_BA, "date", "stress_01"]].head(10))


def main() -> None:
    ensure_dirs()
    df = load_hourly()
    df = repair_demand_spikes(df)
    daily = engineer_daily_features(df)
    daily = add_season_and_filter_year(daily)
    daily = add_stress_scores(daily)

    save_outputs(daily)
    print_sanity_summary(daily)

    plot_timeseries(daily)
    plot_distribution(daily)
    export_top_days(daily)

    try:
        print("\n✅ Module 3 complete.")
    except UnicodeEncodeError:
        print("\nModule 3 complete.")
    print(f"- Daily parquet: {OUTPUT_PARQUET}")
    print(f"- Figures: {FIG_DIR}")


if __name__ == "__main__":
    main()
