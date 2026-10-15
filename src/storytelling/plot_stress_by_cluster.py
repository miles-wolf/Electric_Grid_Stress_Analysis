import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

DATA_PATH = Path("data/processed/unsupervised/daily_with_clusters.parquet")
FIG_DIR = Path("reports/figures/storytelling/02_stress_by_cluster")
FIG_DIR.mkdir(parents=True, exist_ok=True)

BA_COL = "balancing_authority"
CLUSTER_COL = "cluster"
STRESS_COL = "stress_z"


def plot_stress_by_cluster_ax(ax, df_ba: pd.DataFrame, ba_name: str):
    display_name = "CAISO" if ba_name == "CISO" else ba_name

    cluster_order = (
        df_ba.groupby(CLUSTER_COL)[STRESS_COL]
        .mean()
        .sort_values()
        .index
        .tolist()
    )

    data = [df_ba[df_ba[CLUSTER_COL] == c][STRESS_COL].dropna().values for c in cluster_order]

    ax.boxplot(data, showfliers=True)
    ax.set_xticks(range(1, len(cluster_order) + 1))
    ax.set_xticklabels([str(c) for c in cluster_order])

    means = [df_ba[df_ba[CLUSTER_COL] == c][STRESS_COL].mean() for c in cluster_order]
    ax.scatter(range(1, len(means) + 1), means, s=40, marker="D", label="Mean")

    ax.axhline(0, color="gray", linestyle="--", linewidth=1, alpha=0.6)
    ax.set_title(display_name)
    ax.set_xlabel("Cluster (ordered by mean stress)", fontsize=16)
    ax.set_ylabel("Demand Stress (z-score)", fontsize=16)
    ax.legend(loc="upper left")


if __name__ == "__main__":
    df = pd.read_parquet(DATA_PATH)
    bas = sorted(df[BA_COL].unique())

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, ba in zip(axes, bas):
        plot_stress_by_cluster_ax(ax, df[df[BA_COL] == ba], ba)

    ylo, yhi = axes[0].get_ylim()
    axes[0].set_ylim(ylo - 0.5, yhi + 0.5)

    plt.tight_layout()

    outpath = FIG_DIR / "02_stress_by_cluster_combined.png"
    plt.savefig(outpath, dpi=200)
    plt.close()
    print(f"Wrote {outpath}")
