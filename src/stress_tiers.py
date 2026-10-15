"""
Stress Tier Labeling

Adds two derived columns to daily_with_clusters:

  cluster_label  — human-readable regime name derived automatically from
                   cluster properties (mean stress_z rank + season
                   concentration). Replaces the previous hand-maintained
                   CLUSTER_LABELS dict so re-runs don't require manual updates.

  ramp_dominant  — True where z_daily_max_ramp_mw > z_daily_peak_mw.
                   Meaningful mainly within extreme-cluster days; available
                   on all days so Power BI can filter freely.

Also writes data/processed/stress/stress_tier_thresholds.csv — the within-BA
within-season p75/p90 values kept as documentation of where the distribution
breaks, even though event candidacy is now driven by cluster membership rather
than these percentile cuts.

Outputs (updated in-place):
  data/processed/unsupervised/daily_with_clusters.csv
  data/processed/unsupervised/daily_with_clusters.parquet
"""

import pandas as pd
from pathlib import Path

from src.cluster_diagnostics import auto_label_clusters

CLUSTER_CSV     = Path("data/processed/unsupervised/daily_with_clusters.csv")
CLUSTER_PARQUET = Path("data/processed/unsupervised/daily_with_clusters.parquet")
THRESHOLD_PATH  = Path("data/processed/stress/stress_tier_thresholds.csv")

# Seasons where a percentile boundary is meaningful — used only for the
# reference threshold CSV, not for event candidacy.
ACTIVE_SEASONS = {
    "CISO": ["Summer"],
    "PJM":  ["Summer", "Winter"],
}


def add_cluster_labels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    labels = auto_label_clusters(df)
    df["cluster_label"] = df.apply(
        lambda r: labels.get(r["balancing_authority"], {}).get(
            int(r["cluster"]), "Unknown"
        ),
        axis=1,
    )
    return df


def add_ramp_dominant(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ramp_dominant"] = df["z_daily_max_ramp_mw"] > df["z_daily_peak_mw"]
    return df


def compute_reference_thresholds(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ba, seasons in ACTIVE_SEASONS.items():
        for season in seasons:
            grp = df[(df["balancing_authority"] == ba) & (df["season"] == season)]
            if grp.empty:
                continue
            rows.append({
                "balancing_authority": ba,
                "season":              season,
                "n_days":              len(grp),
                "p75":                 round(grp["stress_z"].quantile(0.75), 4),
                "p90":                 round(grp["stress_z"].quantile(0.90), 4),
            })
    return pd.DataFrame(rows)


def main():
    THRESHOLD_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(CLUSTER_CSV)
    df["date"] = pd.to_datetime(df["date"])

    if "season" not in df.columns:
        raise RuntimeError(
            "daily_with_clusters is missing the 'season' column. "
            "Re-run `make stress_daily` and `make unsupervised` to regenerate."
        )

    df = add_cluster_labels(df)
    df = add_ramp_dominant(df)

    print("Auto-derived cluster labels:")
    derived = auto_label_clusters(df)
    for ba, mapping in derived.items():
        print(f"  {ba}: {mapping}")

    print("\nCluster label counts per BA:")
    print(df.groupby(["balancing_authority", "cluster_label"]).size().unstack(fill_value=0))

    extreme_labels = df[df["cluster_label"].str.startswith("Extreme")]
    if not extreme_labels.empty:
        print("\nRamp-dominant days within extreme clusters:")
        print(extreme_labels.groupby(
            ["balancing_authority", "cluster_label", "ramp_dominant"]
        ).size().unstack(fill_value=0))

    thresholds = compute_reference_thresholds(df)
    thresholds.to_csv(THRESHOLD_PATH, index=False)
    print(f"\nReference thresholds (documentation only):")
    print(thresholds.to_string(index=False))

    df.to_csv(CLUSTER_CSV, index=False)
    df.to_parquet(CLUSTER_PARQUET, index=False)
    print(f"\nUpdated {CLUSTER_CSV}")


if __name__ == "__main__":
    main()
