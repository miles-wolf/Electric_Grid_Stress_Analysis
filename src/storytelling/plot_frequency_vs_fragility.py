import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

DATA_PATH = Path("data/processed/unsupervised/daily_with_clusters.parquet")
FIG_DIR = Path("reports/figures/storytelling/03_frequency_vs_fragility")
FIG_DIR.mkdir(parents=True, exist_ok=True)

BA_COL = "balancing_authority"
CLUSTER_COL = "cluster"
FRAG_COL = "fragility_z"


def summarize_by_cluster(df_ba: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df_ba
        .groupby(CLUSTER_COL)
        .agg(
            n_days=(FRAG_COL, "count"),
            mean_fragility=(FRAG_COL, "mean")
        )
        .reset_index()
    )
    total_days = summary["n_days"].sum()
    summary["pct_days"] = summary["n_days"] / total_days * 100
    return summary


def plot_frequency_vs_fragility(ax, summary: pd.DataFrame, ba_name: str):
    display_name = "CAISO" if ba_name == "CISO" else ba_name

    for _, row in summary.iterrows():
        ax.scatter(
            row["pct_days"],
            row["mean_fragility"],
            s=120,
            alpha=0.8,
            label=f"Cluster {int(row[CLUSTER_COL])}"
        )

    ax.axhline(0, color="gray", linestyle="--", linewidth=1, alpha=0.6)
    ax.set_title(display_name)
    ax.set_xlabel("Percent of Days in Regime (%)", fontsize=16)
    ax.grid(alpha=0.3)
    ax.legend(loc="best")


if __name__ == "__main__":
    df = pd.read_parquet(DATA_PATH)
    bas = sorted(df[BA_COL].unique())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for ax, ba in zip(axes, bas):
        summary = summarize_by_cluster(df[df[BA_COL] == ba])
        plot_frequency_vs_fragility(ax, summary, ba)

    axes[0].set_ylabel("Mean Fragility (z-score)", fontsize=16)
    plt.tight_layout()

    outpath = FIG_DIR / "03_frequency_vs_fragility_combined.png"
    plt.savefig(outpath, dpi=200)
    plt.close()
    print(f"Wrote {outpath}")
