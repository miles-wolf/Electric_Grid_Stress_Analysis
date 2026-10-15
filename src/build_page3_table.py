"""
Consolidates all Page 3 source tables into a single wide sparse CSV.

Each row carries a record_type column so Power BI visuals can filter
to their relevant subset while sharing one BA slicer across the page.

record_type values:
  "onset"       — event onset timing (Section 1)
  "composite"   — mean z-score trajectories day -7 to +14 (Section 2)
  "composition" — cluster x season day counts (Section 3 stacked bar)
  "silhouette"  — per-BA silhouette score (Section 3 metric card)
  "centroid"    — cluster centroids in z_peak / z_ramp space (Section 3 scatter)

Output: data/processed/dashboard/page3_data.csv
"""

import pandas as pd
from pathlib import Path

SRC = Path("data/processed")
OUT = SRC / "dashboard" / "page3_data.csv"


def load_onset() -> pd.DataFrame:
    df = pd.read_csv(SRC / "event_composite/event_onset_tiers.csv")
    return pd.DataFrame({
        "balancing_authority": df["balancing_authority"],
        "record_type":         "onset",
        "season":              df["season"],
        "stress_tier":         df["stress_tier"],
        "cluster_label":       pd.NA,
        "component":           df["component"],
        "mean_onset_days":     df["mean_onset"],
        "median_onset_days":   df["median_onset"],
        "n_events_onset":      df["n_events_with_onset"],
        "relative_day":        pd.NA,
        "mean_z_peak":         pd.NA,
        "mean_z_ramp":         pd.NA,
        "mean_stress_z":       pd.NA,
        "std_stress_z":        pd.NA,
        "n_events_composite":  pd.NA,
        "n_days":              pd.NA,
        "season_pct":          pd.NA,
        "silhouette_score":    pd.NA,
        "k_clusters":          pd.NA,
        "centroid_z_peak":     pd.NA,
        "centroid_z_ramp":     pd.NA,
        "n_training_days":     pd.NA,
    })


def load_composite() -> pd.DataFrame:
    df = pd.read_csv(SRC / "event_composite/event_composite_tiers.csv")
    return pd.DataFrame({
        "balancing_authority": df["balancing_authority"],
        "record_type":         "composite",
        "season":              df["season"],
        "stress_tier":         df["stress_tier"],
        "cluster_label":       pd.NA,
        "component":           pd.NA,
        "mean_onset_days":     pd.NA,
        "median_onset_days":   pd.NA,
        "n_events_onset":      pd.NA,
        "relative_day":        df["relative_day"],
        "mean_z_peak":         df["mean_z_daily_peak_mw"],
        "mean_z_ramp":         df["mean_z_daily_max_ramp_mw"],
        "mean_stress_z":       df["mean_stress_z"],
        "std_stress_z":        df["std_stress_z"],
        "n_events_composite":  df["n_events"],
        "n_days":              pd.NA,
        "season_pct":          pd.NA,
        "silhouette_score":    pd.NA,
        "k_clusters":          pd.NA,
        "centroid_z_peak":     pd.NA,
        "centroid_z_ramp":     pd.NA,
        "n_training_days":     pd.NA,
    })


def load_composition() -> pd.DataFrame:
    df = pd.read_csv(SRC / "dashboard/cluster_seasonal_composition.csv")
    return pd.DataFrame({
        "balancing_authority": df["balancing_authority"],
        "record_type":         "composition",
        "season":              df["season"],
        "stress_tier":         pd.NA,
        "cluster_label":       df["cluster_label"],
        "component":           pd.NA,
        "mean_onset_days":     pd.NA,
        "median_onset_days":   pd.NA,
        "n_events_onset":      pd.NA,
        "relative_day":        pd.NA,
        "mean_z_peak":         pd.NA,
        "mean_z_ramp":         pd.NA,
        "mean_stress_z":       pd.NA,
        "std_stress_z":        pd.NA,
        "n_events_composite":  pd.NA,
        "n_days":              df["n_days"],
        "season_pct":          df["pct"],
        "silhouette_score":    pd.NA,
        "k_clusters":          pd.NA,
        "centroid_z_peak":     pd.NA,
        "centroid_z_ramp":     pd.NA,
        "n_training_days":     pd.NA,
    })


def load_silhouette() -> pd.DataFrame:
    df = pd.read_csv(SRC / "dashboard/silhouette_scores.csv")
    return pd.DataFrame({
        "balancing_authority": df["balancing_authority"],
        "record_type":         "silhouette",
        "season":              pd.NA,
        "stress_tier":         pd.NA,
        "cluster_label":       pd.NA,
        "component":           pd.NA,
        "mean_onset_days":     pd.NA,
        "median_onset_days":   pd.NA,
        "n_events_onset":      pd.NA,
        "relative_day":        pd.NA,
        "mean_z_peak":         pd.NA,
        "mean_z_ramp":         pd.NA,
        "mean_stress_z":       pd.NA,
        "std_stress_z":        pd.NA,
        "n_events_composite":  pd.NA,
        "n_days":              pd.NA,
        "season_pct":          pd.NA,
        "silhouette_score":    df["silhouette_score"],
        "k_clusters":          df["k"],
        "centroid_z_peak":     pd.NA,
        "centroid_z_ramp":     pd.NA,
        "n_training_days":     pd.NA,
    })


def load_centroids() -> pd.DataFrame:
    df = pd.read_csv(SRC / "dashboard/cluster_centroids.csv")
    return pd.DataFrame({
        "balancing_authority": df["balancing_authority"],
        "record_type":         "centroid",
        "season":              pd.NA,
        "stress_tier":         pd.NA,
        "cluster_label":       df["cluster_label"],
        "component":           pd.NA,
        "mean_onset_days":     pd.NA,
        "median_onset_days":   pd.NA,
        "n_events_onset":      pd.NA,
        "relative_day":        pd.NA,
        "mean_z_peak":         pd.NA,
        "mean_z_ramp":         pd.NA,
        "mean_stress_z":       df["mean_stress_z"],
        "std_stress_z":        pd.NA,
        "n_events_composite":  pd.NA,
        "n_days":              pd.NA,
        "season_pct":          pd.NA,
        "silhouette_score":    pd.NA,
        "k_clusters":          pd.NA,
        "centroid_z_peak":     df["centroid_z_peak"],
        "centroid_z_ramp":     df["centroid_z_ramp"],
        "n_training_days":     df["n_training_days"],
    })


def main():
    frames = [
        load_onset(),
        load_composite(),
        load_composition(),
        load_silhouette(),
        load_centroids(),
    ]
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(OUT, index=False)

    print(f"Wrote {OUT}  ({len(combined)} rows, {len(combined.columns)} columns)")
    print()
    print("Row counts by record_type:")
    print(combined["record_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
