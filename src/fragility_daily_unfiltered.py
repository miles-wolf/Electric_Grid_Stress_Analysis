"""
Generates unfiltered daily fragility data and time series plot for appendix comparison.
Identical to fragility_daily.py but skips the spike repair step.
"""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.fragility_daily import (
    load_hourly,
    engineer_daily_features,
    add_fragility_scores,
    COL_BA,
)

OUTPUT_PARQUET = Path("data/processed/fragility/daily_fragility_pjm_ciso_2025_unfiltered.parquet")
FIG_DIR = Path("reports/figures/fragility_daily")


def main() -> None:
    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)

    df = load_hourly()
    # spike repair intentionally skipped
    daily = engineer_daily_features(df)
    daily = add_fragility_scores(daily)

    daily.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"Wrote unfiltered parquet: {OUTPUT_PARQUET}")

    # Time series plot
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    bas = sorted(d[COL_BA].unique())

    fig, ax = plt.subplots(figsize=(12, 5))
    for ba in bas:
        sub = d[d[COL_BA] == ba].sort_values("date")
        ba_label = "CAISO" if ba == "CISO" else ba
        ax.plot(sub["date"], sub["fragility_01"], label=ba_label)

    ax.set_ylabel("Fragility (0-1)", fontsize=16)
    ax.set_xlabel("Date", fontsize=16)
    ax.legend(loc="upper right")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
    plt.tight_layout()

    out = FIG_DIR / "fragility_timeseries_unfiltered.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Wrote plot: {out}")


if __name__ == "__main__":
    main()
