"""
K-Selection Justification

Sweeps K-means k=2..8 per BA on [z_peak, z_ramp] and reports:
  - Inertia (elbow method)
  - Silhouette score (geometric cluster quality, higher = better)
  - Davies-Bouldin score (alternative quality metric, lower = better)
  - Calinski-Harabasz score (variance ratio criterion, higher = better)
  - Maximum season concentration achieved by any non-trivial cluster
    (does any value of k produce a winter- or summer-dominated cluster?)

The season-concentration sweep is the key diagnostic for the question
"will a winter regime emerge at higher k?" — if no k produces a cluster
above the labeling threshold for Winter, the answer is empirically no.

Outputs (reports/figures/k_sweep/):
  k_sweep_metrics.csv         — full metrics table for both BAs (report-ready)
  elbow_inertia.png           — inertia vs k, marks chosen k
  cluster_quality_metrics.png — silhouette / DB / CH vs k, both BAs
  season_concentration_by_k.png — max Summer% and Winter% per cluster at each k

Run:
  python -m src.analysis_k_selection
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
    calinski_harabasz_score,
)

from src.config import DAILY_PARQUET_PATH, FEATURE_COLS

K_RANGE = range(2, 9)
RANDOM_STATE = 42
N_INIT = 20
MIN_CLUSTER_SIZE = 5  # ignore tiny clusters when computing season concentration
LABEL_THRESHOLD = 0.65

OUTPUT_DIR = Path("reports/figures/k_sweep")


def sweep_k_for_ba(ba_df: pd.DataFrame, k_range=K_RANGE) -> pd.DataFrame:
    """Sweep k for one BA. Returns a metrics table indexed by k."""
    X = ba_df[FEATURE_COLS].values
    season = ba_df["season"].values

    rows = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=N_INIT).fit(X)
        labels = km.labels_

        # Compute max season concentration across non-trivial clusters
        max_summer = 0.0
        max_winter = 0.0
        non_trivial = 0
        for c in range(k):
            mask = labels == c
            n = mask.sum()
            if n < MIN_CLUSTER_SIZE:
                continue
            non_trivial += 1
            cs = season[mask]
            max_summer = max(max_summer, (cs == "Summer").mean())
            max_winter = max(max_winter, (cs == "Winter").mean())

        rows.append({
            "k": k,
            "inertia": round(km.inertia_, 3),
            "silhouette": round(silhouette_score(X, labels), 4),
            "davies_bouldin": round(davies_bouldin_score(X, labels), 4),
            "calinski_harabasz": round(calinski_harabasz_score(X, labels), 2),
            "max_summer_pct": round(max_summer * 100, 1),
            "max_winter_pct": round(max_winter * 100, 1),
            "n_clusters_nontrivial": non_trivial,
        })
    return pd.DataFrame(rows)


def make_elbow_plot(metrics_by_ba: dict, output_path: Path, chosen_k: int = 4):
    fig, axes = plt.subplots(1, len(metrics_by_ba), figsize=(6 * len(metrics_by_ba), 5))
    if len(metrics_by_ba) == 1:
        axes = [axes]
    for ax, (ba, df) in zip(axes, metrics_by_ba.items()):
        ax.plot(df["k"], df["inertia"], "o-", color="tab:blue", linewidth=2)
        ax.axvline(chosen_k, color="red", linestyle="--", alpha=0.6,
                   label=f"chosen k = {chosen_k}")
        ax.set_xlabel("k (number of clusters)")
        ax.set_ylabel("Inertia (within-cluster sum of squares)")
        ax.set_title(f"{ba}: Elbow plot")
        ax.legend()
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {output_path}")


def make_quality_plot(metrics_by_ba: dict, output_path: Path, chosen_k: int = 4):
    fig, axes = plt.subplots(3, len(metrics_by_ba),
                              figsize=(6 * len(metrics_by_ba), 12))
    if len(metrics_by_ba) == 1:
        axes = axes.reshape(3, 1)

    for col, (ba, df) in enumerate(metrics_by_ba.items()):
        # Silhouette (higher = better)
        ax = axes[0, col]
        ax.plot(df["k"], df["silhouette"], "o-", color="tab:green", linewidth=2)
        ax.axvline(chosen_k, color="red", linestyle="--", alpha=0.6,
                   label=f"chosen k = {chosen_k}")
        ax.set_xlabel("k")
        ax.set_ylabel("Silhouette score")
        ax.set_title(f"{ba}: Silhouette (higher = better, peaks at optimal k)")
        ax.legend()
        ax.grid(alpha=0.3)

        # Davies-Bouldin (lower = better)
        ax = axes[1, col]
        ax.plot(df["k"], df["davies_bouldin"], "o-", color="tab:orange", linewidth=2)
        ax.axvline(chosen_k, color="red", linestyle="--", alpha=0.6,
                   label=f"chosen k = {chosen_k}")
        ax.set_xlabel("k")
        ax.set_ylabel("Davies-Bouldin score")
        ax.set_title(f"{ba}: Davies-Bouldin (lower = better)")
        ax.legend()
        ax.grid(alpha=0.3)

        # Calinski-Harabasz (higher = better)
        ax = axes[2, col]
        ax.plot(df["k"], df["calinski_harabasz"], "o-", color="tab:purple", linewidth=2)
        ax.axvline(chosen_k, color="red", linestyle="--", alpha=0.6,
                   label=f"chosen k = {chosen_k}")
        ax.set_xlabel("k")
        ax.set_ylabel("Calinski-Harabasz score")
        ax.set_title(f"{ba}: Calinski-Harabasz (higher = better)")
        ax.legend()
        ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {output_path}")


def make_season_concentration_plot(metrics_by_ba: dict, output_path: Path,
                                   threshold: float = LABEL_THRESHOLD):
    fig, axes = plt.subplots(1, len(metrics_by_ba),
                              figsize=(6 * len(metrics_by_ba), 5), sharey=True)
    if len(metrics_by_ba) == 1:
        axes = [axes]
    for ax, (ba, df) in zip(axes, metrics_by_ba.items()):
        ax.plot(df["k"], df["max_summer_pct"], "o-", color="tab:red",
                linewidth=2, label="Max Summer % in any cluster")
        ax.plot(df["k"], df["max_winter_pct"], "o-", color="tab:blue",
                linewidth=2, label="Max Winter % in any cluster")
        ax.axhline(threshold * 100, color="gray", linestyle="--", alpha=0.6,
                   label=f"{int(threshold * 100)}% label threshold")
        ax.set_xlabel("k")
        ax.set_ylabel("Highest season concentration (%)")
        ax.set_title(f"{ba}: Can any k produce a season-dominated cluster?")
        ax.set_ylim(0, 105)
        ax.legend(loc="best")
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {output_path}")


def print_verdict(metrics_by_ba: dict, threshold: float = LABEL_THRESHOLD):
    print("\n" + "=" * 60)
    print("  VERDICT: does any k produce a winter-dominated cluster?")
    print("=" * 60)
    for ba, df in metrics_by_ba.items():
        winter_qualifies = df[df["max_winter_pct"] >= threshold * 100]
        if winter_qualifies.empty:
            best_k = df.loc[df["max_winter_pct"].idxmax(), "k"]
            best_pct = df["max_winter_pct"].max()
            print(f"  {ba}: NO. Best max-winter is {best_pct:.1f}% at k={int(best_k)} "
                  f"(threshold for labeling: {int(threshold * 100)}%).")
        else:
            qualifying_ks = winter_qualifies["k"].tolist()
            print(f"  {ba}: YES. Winter-dominated cluster appears at k = {qualifying_ks}.")
    print("=" * 60)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(DAILY_PARQUET_PATH)
    df["date"] = pd.to_datetime(df["date"])

    if "season" not in df.columns:
        raise RuntimeError(
            "season column missing — re-run `make stress_daily` first."
        )

    metrics_by_ba = {}
    for ba, ba_df in df.groupby("balancing_authority"):
        print(f"\n=== Sweeping k for {ba} ===")
        m = sweep_k_for_ba(ba_df)
        m.insert(0, "balancing_authority", ba)
        print(m.to_string(index=False))
        metrics_by_ba[ba] = m

    combined = pd.concat(metrics_by_ba.values(), ignore_index=True)
    combined.to_csv(OUTPUT_DIR / "k_sweep_metrics.csv", index=False)
    print(f"\nWrote {OUTPUT_DIR / 'k_sweep_metrics.csv'}")

    make_elbow_plot(metrics_by_ba, OUTPUT_DIR / "elbow_inertia.png", chosen_k=4)
    make_quality_plot(metrics_by_ba, OUTPUT_DIR / "cluster_quality_metrics.png", chosen_k=4)
    make_season_concentration_plot(metrics_by_ba, OUTPUT_DIR / "season_concentration_by_k.png")

    print_verdict(metrics_by_ba)


if __name__ == "__main__":
    main()
