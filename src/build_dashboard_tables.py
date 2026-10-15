"""
Builds Power BI data tables for dashboard Page 3.

  data/processed/dashboard/
    cluster_seasonal_composition.csv  — cluster x season day counts (Section 3)
    cluster_centroids_labelled.csv    — centroid scatter source (already exists
                                        in operational/, copied/renamed here)
    silhouette_scores.csv             — metric cards for validation callout

Also writes:
  reports/figures/storytelling/appendix_hourly/
    A3_cluster_seasonal_composition.png
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

from src.cluster_diagnostics import auto_label_clusters, silhouette_per_ba

CLUSTER_PARQUET  = Path("data/processed/unsupervised/daily_with_clusters.parquet")
K_SWEEP_PATH     = Path("reports/figures/k_sweep/k_sweep_metrics.csv")
CENTROIDS_PATH   = Path("data/processed/operational/cluster_centroids_2025.csv")
OUT_DATA         = Path("data/processed/dashboard")
FIG_DIR          = Path("reports/figures/storytelling/appendix_hourly")

OUT_DATA.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

SEASON_ORDER  = ["Summer", "Shoulder", "Winter"]
SEASON_COLORS = {"Summer": "#E07B39", "Shoulder": "#5BAD72", "Winter": "#4A90C4"}
BA_DISPLAY    = {"CISO": "CAISO", "PJM": "PJM"}
TIER_ORDER    = ["Stable", "Moderate", "Elevated", "Extreme"]


# ---------------------------------------------------------------------------
# Cluster seasonal composition table + figure
# ---------------------------------------------------------------------------

def build_seasonal_composition(df: pd.DataFrame) -> pd.DataFrame:
    labels = auto_label_clusters(df)   # {ba: {cluster_int: label}}

    df = df.copy()
    df["cluster_label"] = df.apply(
        lambda r: labels[r["balancing_authority"]].get(int(r["cluster"]), "Unknown"),
        axis=1,
    )

    counts = (
        df.groupby(["balancing_authority", "cluster_label", "season"])
        .size()
        .reset_index(name="n_days")
    )
    totals = counts.groupby(
        ["balancing_authority", "cluster_label"]
    )["n_days"].transform("sum")
    counts["pct"] = (counts["n_days"] / totals * 100).round(1)
    return counts


def plot_seasonal_composition(counts: pd.DataFrame):
    bas = ["CISO", "PJM"]
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=False)

    for ax, ba in zip(axes, bas):
        ba_data = counts[counts["balancing_authority"] == ba].copy()

        # Order clusters by tier
        ba_data["tier_order"] = ba_data["cluster_label"].map(
            {t: i for i, t in enumerate(TIER_ORDER)}
        )
        ba_data = ba_data.sort_values("tier_order")
        cluster_labels = ba_data["cluster_label"].unique().tolist()
        cluster_labels.sort(key=lambda x: TIER_ORDER.index(x) if x in TIER_ORDER else 99)

        x = range(len(cluster_labels))
        bottoms = {cl: 0 for cl in cluster_labels}

        for season in SEASON_ORDER:
            heights = []
            for cl in cluster_labels:
                row = ba_data[
                    (ba_data["cluster_label"] == cl) & (ba_data["season"] == season)
                ]
                heights.append(int(row["n_days"].values[0]) if not row.empty else 0)

            bars = ax.bar(
                x, heights,
                bottom=[bottoms[cl] for cl in cluster_labels],
                color=SEASON_COLORS[season],
                label=season,
                width=0.55,
                edgecolor="white",
                linewidth=0.5,
            )

            # Label each non-zero segment
            for rect, cl, h in zip(bars, cluster_labels, heights):
                if h == 0:
                    continue
                cy = bottoms[cl] + h / 2
                ax.text(
                    rect.get_x() + rect.get_width() / 2,
                    cy,
                    str(h),
                    ha="center", va="center",
                    fontsize=11, fontweight="bold", color="white",
                )
                bottoms[cl] += h

        # n= annotation above each bar
        for i, cl in enumerate(cluster_labels):
            total = bottoms[cl]
            ax.text(
                i, total + 1.5, f"n={total}",
                ha="center", va="bottom", fontsize=9, color="#444444",
            )

        ax.set_xticks(list(x))
        ax.set_xticklabels(cluster_labels, fontsize=12)
        ax.set_ylabel("Days", fontsize=13)
        ax.set_title(BA_DISPLAY[ba], fontsize=17, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)

        if ba == "CISO":
            legend_patches = [
                mpatches.Patch(color=SEASON_COLORS[s], label=s)
                for s in SEASON_ORDER
            ]
            ax.legend(handles=legend_patches, title="Season", fontsize=10,
                      title_fontsize=10, loc="upper right")

    fig.suptitle(
        "Cluster Seasonal Composition\n"
        "How each regime maps to Summer / Shoulder / Winter",
        fontsize=14, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    out = FIG_DIR / "A3_cluster_seasonal_composition.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {out}")


# ---------------------------------------------------------------------------
# Silhouette score cards
# ---------------------------------------------------------------------------

def build_silhouette_table(df: pd.DataFrame) -> pd.DataFrame:
    scores = silhouette_per_ba(df)
    rows = [
        {"balancing_authority": ba, "silhouette_score": score, "k": 4}
        for ba, score in scores.items()
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    df = pd.read_parquet(CLUSTER_PARQUET)
    df["date"] = pd.to_datetime(df["date"])

    # Seasonal composition
    counts = build_seasonal_composition(df)
    counts.to_csv(OUT_DATA / "cluster_seasonal_composition.csv", index=False)
    print(f"Wrote {OUT_DATA}/cluster_seasonal_composition.csv  ({len(counts)} rows)")
    plot_seasonal_composition(counts)

    # Silhouette scores
    sil = build_silhouette_table(df)
    sil.to_csv(OUT_DATA / "silhouette_scores.csv", index=False)
    print(f"Wrote {OUT_DATA}/silhouette_scores.csv")
    print(sil.to_string(index=False))

    # Centroids (copy to dashboard folder for a single import location)
    if CENTROIDS_PATH.exists():
        import shutil
        shutil.copy(CENTROIDS_PATH, OUT_DATA / "cluster_centroids.csv")
        print(f"Copied cluster_centroids.csv to {OUT_DATA}/")


if __name__ == "__main__":
    main()
