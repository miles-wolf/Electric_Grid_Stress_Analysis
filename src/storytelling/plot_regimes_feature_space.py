import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

DATA_PATH = Path("data/processed/unsupervised/daily_with_clusters.parquet")
FIG_DIR = Path("reports/figures/storytelling/01_regimes_feature_space")
FIG_DIR.mkdir(parents=True, exist_ok=True)

X_COL = "z_daily_peak_mw"
Y_COL = "z_daily_max_ramp_mw"
CLUSTER_COL = "cluster"
BA_COL = "balancing_authority"

CLIP_Y_MIN, CLIP_Y_MAX = -3, 4


def plot_feature_space_ax(ax, df_ba: pd.DataFrame, ba_name: str):
    display_name = "CAISO" if ba_name == "CISO" else ba_name

    clip_applied = False
    if ba_name.upper() == "CISO" and df_ba[Y_COL].max() > CLIP_Y_MAX:
        clip_applied = True

    clusters = sorted(df_ba[CLUSTER_COL].unique())
    handles, labels = [], []

    for c in clusters:
        sub = df_ba[df_ba[CLUSTER_COL] == c]
        if clip_applied:
            sub = sub[(sub[Y_COL] >= CLIP_Y_MIN) & (sub[Y_COL] <= CLIP_Y_MAX)]
            if sub.empty:
                continue

        sc = ax.scatter(sub[X_COL], sub[Y_COL], s=40, alpha=0.7, label=str(c))
        handles.append(sc)
        labels.append(str(c))

    if clip_applied:
        ax.set_ylim(CLIP_Y_MIN, CLIP_Y_MAX)

    ax.axhline(0, color="gray", linewidth=1, linestyle="--", alpha=0.5)
    ax.axvline(0, color="gray", linewidth=1, linestyle="--", alpha=0.5)

    ax.set_title(display_name)
    ax.set_xlabel("Daily Peak Load (z-score)", fontsize=16)
    ax.set_ylabel("Daily Max Ramp (z-score)", fontsize=16)
    ax.legend(handles, labels, title="Cluster", loc="lower right")


if __name__ == "__main__":
    df = pd.read_parquet(DATA_PATH)
    bas = sorted(df[BA_COL].unique())

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, ba in zip(axes, bas):
        plot_feature_space_ax(ax, df[df[BA_COL] == ba], ba)

    plt.tight_layout()

    outpath = FIG_DIR / "regimes_feature_space_combined.png"
    plt.savefig(outpath, dpi=200)
    plt.close()
    print(f"Wrote {outpath}")
