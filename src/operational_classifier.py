"""
Operational Day Classifier — Reference Data for Dashboard

Generates reference data for a Power BI / Tableau dashboard feature that
classifies a new day's grid stress regime given raw daily peak and ramp
inputs. The math itself lives in the dashboard (DAX / calculated fields);
this module produces the constants the dashboard needs.

Reference outputs (data/processed/operational/):
  baseline_stats_2025.csv     — per-BA mean/std for daily_peak_mw and
                                daily_max_ramp_mw. Dashboard uses these
                                to z-score a new day's raw inputs against
                                the prior-year distribution.
  cluster_centroids_2025.csv  — per-BA k-means centroids in (z_peak, z_ramp)
                                space with auto-derived labels. Dashboard
                                uses these for nearest-centroid lookup.

A Python reference function classify_day() is included so DAX or Tableau
calculations can be verified against the canonical Python implementation.

Run:
  python -m src.operational_classifier
"""

import pandas as pd
import numpy as np
from pathlib import Path

from src.config import DAILY_PARQUET_PATH
from src.cluster_diagnostics import auto_label_clusters

DAILY_WITH_CLUSTERS = Path("data/processed/unsupervised/daily_with_clusters.parquet")
OUTPUT_DIR = Path("data/processed/operational")

FEATURE_RAW_COLS = ["daily_peak_mw", "daily_max_ramp_mw"]


def compute_baseline_stats(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Per-BA mean and std (population, ddof=0) for the raw features. These
    are the constants the dashboard applies to z-score new daily inputs.
    Uses ddof=0 to match stress_daily.add_stress_scores.
    """
    rows = []
    for ba, ba_df in daily.groupby("balancing_authority"):
        year = int(ba_df["date"].dt.year.mode().iloc[0])
        for feature in FEATURE_RAW_COLS:
            rows.append({
                "balancing_authority": ba,
                "feature":              feature,
                "mean":                 round(float(ba_df[feature].mean()), 4),
                "std":                  round(float(ba_df[feature].std(ddof=0)), 4),
                "n_days_training":      int(len(ba_df)),
                "training_year":        year,
            })
    return pd.DataFrame(rows)


def compute_cluster_centroids(daily_with_clusters: pd.DataFrame) -> pd.DataFrame:
    """
    Per-BA cluster centroids in (z_peak, z_ramp) space with auto labels.
    The centroid of a k-means cluster equals the mean of its members, so
    we compute the centroid directly from the labeled data without re-fitting.
    """
    labels = auto_label_clusters(daily_with_clusters)
    rows = []
    for ba, ba_df in daily_with_clusters.groupby("balancing_authority"):
        ba_labels = labels.get(ba, {})
        for cid, sub in ba_df.groupby("cluster"):
            rows.append({
                "balancing_authority": ba,
                "cluster":             int(cid),
                "cluster_label":       ba_labels.get(int(cid), "Unknown"),
                "centroid_z_peak":     round(float(sub["z_daily_peak_mw"].mean()), 4),
                "centroid_z_ramp":     round(float(sub["z_daily_max_ramp_mw"].mean()), 4),
                "mean_stress_z":       round(float(sub["stress_z"].mean()), 4),
                "n_training_days":     int(len(sub)),
            })
    return (
        pd.DataFrame(rows)
        .sort_values(["balancing_authority", "mean_stress_z"])
        .reset_index(drop=True)
    )


def classify_day(
    ba: str,
    peak_mw: float,
    ramp_mw: float,
    baseline_stats: pd.DataFrame,
    centroids: pd.DataFrame,
) -> dict:
    """
    Reference Python implementation. Mirrors what the dashboard should
    compute step-for-step:

      1. Look up baseline mean/std for this BA.
      2. z_peak = (peak_mw - mean_peak) / std_peak
         z_ramp = (ramp_mw - mean_ramp) / std_ramp
      3. stress_z = z_peak + z_ramp
      4. For each cluster in this BA, compute Euclidean distance from
         (z_peak, z_ramp) to its centroid.
      5. Assign the cluster with minimum distance; return its label.
    """
    ba_stats = baseline_stats[baseline_stats["balancing_authority"] == ba]
    peak_row = ba_stats[ba_stats["feature"] == "daily_peak_mw"].iloc[0]
    ramp_row = ba_stats[ba_stats["feature"] == "daily_max_ramp_mw"].iloc[0]

    z_peak = (peak_mw - peak_row["mean"]) / peak_row["std"]
    z_ramp = (ramp_mw - ramp_row["mean"]) / ramp_row["std"]
    stress_z = z_peak + z_ramp

    ba_centroids = centroids[centroids["balancing_authority"] == ba].copy()
    ba_centroids["distance"] = np.sqrt(
        (ba_centroids["centroid_z_peak"] - z_peak) ** 2 +
        (ba_centroids["centroid_z_ramp"] - z_ramp) ** 2
    )
    nearest = ba_centroids.loc[ba_centroids["distance"].idxmin()]

    return {
        "ba":                    ba,
        "input_peak_mw":         peak_mw,
        "input_ramp_mw":         ramp_mw,
        "z_peak":                round(z_peak, 3),
        "z_ramp":                round(z_ramp, 3),
        "stress_z":              round(stress_z, 3),
        "assigned_cluster":      int(nearest["cluster"]),
        "assigned_label":        nearest["cluster_label"],
        "distance_to_centroid":  round(float(nearest["distance"]), 3),
    }


def print_dashboard_integration_notes(baseline_stats: pd.DataFrame,
                                      centroids: pd.DataFrame):
    """Print a how-to-use summary so the user has it on screen each run."""
    print("\n" + "=" * 72)
    print("  DASHBOARD INTEGRATION NOTES")
    print("=" * 72)
    print("""
The dashboard needs two parameters (the new day's raw inputs) and the two
reference CSVs. The chain of calculation it performs:

  Step 1: Z-score the inputs against the baseline
    z_peak  = (today_peak_mw  - mean_peak)  / std_peak
    z_ramp  = (today_ramp_mw  - mean_ramp)  / std_ramp
    where (mean, std) come from baseline_stats_2025.csv for the selected BA.

  Step 2: Compute the composite stress index
    stress_z = z_peak + z_ramp

  Step 3: Assign nearest cluster centroid
    For each cluster row in cluster_centroids_2025.csv (filtered to the BA):
      distance = sqrt((centroid_z_peak - z_peak)^2 + (centroid_z_ramp - z_ramp)^2)
    Pick the row with minimum distance. That row's cluster_label is the regime.

POWER BI / DAX EXAMPLE (assuming today's inputs are in [Inputs] table):

  z_peak_today =
    DIVIDE(
      [today_peak_mw] -
        CALCULATE(MAX(BaselineStats[mean]),
                  BaselineStats[balancing_authority] = [selected_ba],
                  BaselineStats[feature] = "daily_peak_mw"),
      CALCULATE(MAX(BaselineStats[std]),
                BaselineStats[balancing_authority] = [selected_ba],
                BaselineStats[feature] = "daily_peak_mw")
    )

  assigned_label =
    VAR zp = [z_peak_today]
    VAR zr = [z_ramp_today]
    VAR baCentroids =
      FILTER(ClusterCentroids,
             ClusterCentroids[balancing_authority] = [selected_ba])
    VAR withDist =
      ADDCOLUMNS(baCentroids,
                 "dist", SQRT(([centroid_z_peak] - zp)^2 +
                              ([centroid_z_ramp] - zr)^2))
    VAR minDist = MINX(withDist, [dist])
    RETURN
      MAXX(FILTER(withDist, [dist] = minDist), [cluster_label])

TABLEAU EQUIVALENT (calculated field):

  Use the same structure: LOOKUP into baseline_stats for mean/std,
  z-score the inputs, then a level-of-detail expression to compute
  distance to each centroid and INDEX/MIN to pick the nearest.
""")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    daily = pd.read_parquet(DAILY_PARQUET_PATH)
    daily["date"] = pd.to_datetime(daily["date"])
    with_clusters = pd.read_parquet(DAILY_WITH_CLUSTERS)

    baseline_stats = compute_baseline_stats(daily)
    centroids      = compute_cluster_centroids(with_clusters)

    baseline_stats.to_csv(OUTPUT_DIR / "baseline_stats_2025.csv", index=False)
    centroids.to_csv(OUTPUT_DIR / "cluster_centroids_2025.csv", index=False)

    print("\n=== Baseline Statistics (for z-scoring new days) ===")
    print(baseline_stats.to_string(index=False))

    print("\n=== Cluster Centroids (for nearest-centroid assignment) ===")
    print(centroids.to_string(index=False))

    # Sanity check: run the reference classifier on the top-stress day from
    # training and confirm it lands in the same cluster as stored.
    print("\n=== Reference Classification Tests ===")
    for ba, ba_df in with_clusters.groupby("balancing_authority"):
        demo = ba_df.sort_values("stress_z", ascending=False).iloc[0]
        result = classify_day(
            ba=demo["balancing_authority"],
            peak_mw=demo["daily_peak_mw"],
            ramp_mw=demo["daily_max_ramp_mw"],
            baseline_stats=baseline_stats,
            centroids=centroids,
        )
        match = "OK" if result["assigned_cluster"] == int(demo["cluster"]) else "MISMATCH"
        print(f"\n  [{ba}] Highest-stress training day = {demo['date'].date()}")
        print(f"    stored cluster:   {int(demo['cluster'])} "
              f"(stress_z={demo['stress_z']:.2f})")
        print(f"    classifier said:  {result['assigned_cluster']} "
              f"({result['assigned_label']}, stress_z={result['stress_z']:.2f})  -> {match}")

    print(f"\nWrote {OUTPUT_DIR / 'baseline_stats_2025.csv'}")
    print(f"Wrote {OUTPUT_DIR / 'cluster_centroids_2025.csv'}")

    print_dashboard_integration_notes(baseline_stats, centroids)


if __name__ == "__main__":
    main()
