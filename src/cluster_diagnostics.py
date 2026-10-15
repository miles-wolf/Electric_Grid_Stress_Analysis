"""
Cluster Diagnostics

Auto-derives cluster labels and extreme-cluster identification from the
clustered output produced by src.unsupervised. Removes the need to
manually maintain CLUSTER_LABELS / EXTREME_CLUSTERS dictionaries that
previously had to be updated after every re-run.

Public functions:
  auto_label_clusters(df)        -> {ba: {cluster_int: label_str}}
  derive_extreme_clusters(df)    -> {ba: {season: cluster_int}}
  silhouette_per_ba(df)          -> {ba: silhouette_score}
  validation_report(df, out)     -> writes a one-page markdown summary

Run standalone:
  python -m src.cluster_diagnostics
"""

import pandas as pd
from pathlib import Path
from sklearn.metrics import silhouette_score

from src.config import FEATURE_COLS

CLUSTER_CSV     = Path("data/processed/unsupervised/daily_with_clusters.csv")
CLUSTER_PARQUET = Path("data/processed/unsupervised/daily_with_clusters.parquet")
DEFAULT_REPORT  = Path("reports/diagnostics/cluster_diagnostics.md")

TIER_NAMES = ("Stable", "Moderate", "Elevated", "Extreme")
SEASON_CONCENTRATION_THRESHOLD = 0.65


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def auto_label_clusters(
    df: pd.DataFrame,
    tier_names=TIER_NAMES,
) -> dict:
    """
    Returns {ba: {cluster_int: label_str}}.

    Tier names assigned purely by mean stress_z rank (ascending). No
    season suffix — at k=4 with [z_peak, z_ramp] features, seasonal
    concentration within clusters is not clean enough to label reliably
    (PJM's top cluster is only 80% summer; PJM Elevated is split 46/46
    winter/summer). Operators infer seasonal context from the calendar.
    """
    labels = {}
    for ba, ba_df in df.groupby("balancing_authority"):
        means = ba_df.groupby("cluster")["stress_z"].mean().sort_values()
        cluster_order = list(means.index)

        ba_labels = {}
        for i, cid in enumerate(cluster_order):
            base = tier_names[i] if i < len(tier_names) else f"Tier{i+1}"
            ba_labels[cid] = base

        labels[ba] = {int(c): v for c, v in ba_labels.items()}
    return labels


def derive_extreme_clusters(
    df: pd.DataFrame,
    seasons=("Summer", "Winter"),
    season_concentration_threshold: float = SEASON_CONCENTRATION_THRESHOLD,
) -> dict:
    """
    Returns {ba: {season: cluster_int}}.

    For each (BA, season), picks the cluster with the highest mean stress_z
    whose days are at least season_concentration_threshold in that season.
    Drops (BA, season) entries where no qualifying cluster exists (e.g.
    CISO typically has no winter-concentrated cluster).
    """
    result = {}
    for ba, ba_df in df.groupby("balancing_authority"):
        ba_extremes = {}
        cluster_profiles = ba_df.groupby("cluster").agg(
            mean_stress=("stress_z", "mean"),
            n_days=("date", "count"),
        )
        season_counts = (
            ba_df.groupby(["cluster", "season"])
            .size()
            .unstack(fill_value=0)
        )
        season_share = season_counts.div(season_counts.sum(axis=1), axis=0)

        for season in seasons:
            if season not in season_share.columns:
                continue
            qualifying = cluster_profiles[
                season_share[season] >= season_concentration_threshold
            ]
            if qualifying.empty:
                continue
            extreme_cid = qualifying["mean_stress"].idxmax()
            ba_extremes[season] = int(extreme_cid)

        if ba_extremes:
            result[ba] = ba_extremes
    return result


def silhouette_per_ba(df: pd.DataFrame, feature_cols=FEATURE_COLS) -> dict:
    """
    Silhouette score per BA. Higher = tighter, better-separated clusters
    (range -1 to 1; ~0.5+ is considered good in 2D).
    """
    scores = {}
    for ba, ba_df in df.groupby("balancing_authority"):
        if ba_df["cluster"].nunique() < 2:
            scores[ba] = None
            continue
        X = ba_df[feature_cols].values
        labels = ba_df["cluster"].values
        scores[ba] = round(float(silhouette_score(X, labels)), 3)
    return scores


# ---------------------------------------------------------------------------
# Markdown validation report
# ---------------------------------------------------------------------------

def validation_report(
    df: pd.DataFrame,
    output_path: Path = DEFAULT_REPORT,
) -> Path:
    """
    Write a one-page markdown summary: per-BA cluster table with tier label,
    size, stress stats, season composition, silhouette, and derived extreme
    clusters. Designed to replace eyeballing 4 CSVs after each re-run.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    labels = auto_label_clusters(df)
    extremes = derive_extreme_clusters(df)
    silhouettes = silhouette_per_ba(df)

    lines = [
        "# Cluster Diagnostics Report",
        "",
        f"_Auto-derived from `{CLUSTER_CSV.name}` "
        f"({len(df)} rows, {df['balancing_authority'].nunique()} BA(s))._",
        "",
    ]

    for ba in sorted(df["balancing_authority"].unique()):
        ba_df = df[df["balancing_authority"] == ba]
        lines.append(f"## {ba}")
        lines.append("")
        lines.append(f"- Silhouette score: **{silhouettes.get(ba)}** "
                     f"(higher = tighter clusters; range -1 to 1)")
        lines.append("")

        cluster_order = (
            ba_df.groupby("cluster")["stress_z"].mean().sort_values().index
        )

        cols = ["cluster", "label", "n_days", "mean_stress_z",
                "max_stress_z", "season_mix"]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join("---" for _ in cols) + "|")
        for cid in cluster_order:
            sub = ba_df[ba_df["cluster"] == cid]
            season_share = sub["season"].value_counts(normalize=True)
            season_str = ", ".join(
                f"{s} {pct:.0%}" for s, pct in season_share.items()
            )
            row = [
                str(int(cid)),
                labels[ba][int(cid)],
                str(len(sub)),
                f"{sub['stress_z'].mean():.2f}",
                f"{sub['stress_z'].max():.2f}",
                season_str,
            ]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

        ba_extremes = extremes.get(ba, {})
        if ba_extremes:
            parts = [
                f"{season} → cluster {cid} ({labels[ba][cid]})"
                for season, cid in ba_extremes.items()
            ]
            lines.append("**Extreme clusters by season:** " + " | ".join(parts))
        else:
            lines.append("**Extreme clusters by season:** none detected")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote diagnostics report: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    if CLUSTER_PARQUET.exists():
        df = pd.read_parquet(CLUSTER_PARQUET)
    else:
        df = pd.read_csv(CLUSTER_CSV)
    df["date"] = pd.to_datetime(df["date"])

    print("\n=== Auto-derived cluster labels ===")
    labels = auto_label_clusters(df)
    for ba, ba_labels in labels.items():
        print(f"\n{ba}:")
        for cid in sorted(ba_labels):
            print(f"  cluster {cid} -> {ba_labels[cid]}")

    print("\n=== Auto-derived extreme clusters ===")
    extremes = derive_extreme_clusters(df)
    for ba, season_map in extremes.items():
        print(f"  {ba}: {season_map}")

    print("\n=== Silhouette scores ===")
    for ba, s in silhouette_per_ba(df).items():
        print(f"  {ba}: {s}")

    validation_report(df)


if __name__ == "__main__":
    main()
