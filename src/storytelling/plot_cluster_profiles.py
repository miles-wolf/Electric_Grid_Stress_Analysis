"""
Storytelling Module 6: Cluster Profile Analytics

Generates two figures into reports/figures/storytelling/06_cluster_profiles/:

  06_cluster_scatter.png   — z_load vs z_ramp scatter per BA, colored by cluster_label,
                              with a diagonal parity line (ramp = load) and ramp_dominant
                              flag encoded as filled (ramp > load) vs hollow (load > ramp)
                              markers. Extreme cluster days labeled separately.

  06_cluster_composition.png — stacked bar charts showing seasonal composition of each
                                cluster per BA, so the "Elevated Winter" label is visually
                                justified and differences in summer/winter/shoulder mix
                                are immediately readable.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

CLUSTER_CSV = Path("data/processed/unsupervised/daily_with_clusters.csv")
FIG_DIR     = Path("reports/figures/storytelling/06_cluster_profiles")
FIG_DIR.mkdir(parents=True, exist_ok=True)

BAS        = ["CISO", "PJM"]
BA_DISPLAY = {"CISO": "CAISO", "PJM": "PJM"}

# Ordered from least to most stressed — controls legend and bar order
LABEL_ORDER = {
    "CISO": ["Stable", "Moderate", "Elevated", "Extreme Summer"],
    "PJM":  ["Stable", "Moderate", "Elevated Winter", "Extreme Summer"],
}

CLUSTER_COLORS = {
    "Stable":         "#a8d8ea",
    "Moderate":       "#f9c74f",
    "Elevated":       "#f77f00",
    "Elevated Winter":"#7b2d8b",
    "Extreme Summer": "#d62728",
}

SEASON_COLORS = {
    "Summer":  "#e07b39",
    "Shoulder":"#7cbf8e",
    "Winter":  "#5a9abf",
}
SEASON_ORDER = ["Summer", "Shoulder", "Winter"]

SEASON_MAP = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Shoulder", 4: "Shoulder", 5: "Shoulder",
    6: "Summer", 7: "Summer", 8: "Summer", 9: "Summer",
    10: "Shoulder", 11: "Shoulder",
}


# ---------------------------------------------------------------------------
# Figure 1: z_load vs z_ramp scatter with parity line
# ---------------------------------------------------------------------------

def plot_cluster_scatter(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=False)

    for ax, ba in zip(axes, BAS):
        sub = df[df["balancing_authority"] == ba].copy()

        # Draw diagonal parity line first (behind points)
        lim_min = min(sub["z_daily_peak_mw"].min(), sub["z_daily_max_ramp_mw"].min()) - 0.3
        lim_max = max(sub["z_daily_peak_mw"].max(), sub["z_daily_max_ramp_mw"].max()) + 0.3
        ax.plot([lim_min, lim_max], [lim_min, lim_max],
                color="gray", lw=1.2, ls="--", alpha=0.5, label="Ramp = Load (parity)")

        for label in LABEL_ORDER[ba]:
            grp = sub[sub["cluster_label"] == label]
            if grp.empty:
                continue

            color  = CLUSTER_COLORS[label]
            is_ext = (label in ("Extreme Summer", "Elevated Winter"))
            size   = 55 if is_ext else 35
            alpha  = 0.85 if is_ext else 0.55

            # Ramp-dominant days: filled circle; load-dominant: hollow diamond
            ramp_dom  = grp[grp["ramp_dominant"] == True]
            load_dom  = grp[grp["ramp_dominant"] == False]

            ax.scatter(
                load_dom["z_daily_peak_mw"], load_dom["z_daily_max_ramp_mw"],
                color="none", edgecolors=color, s=size, alpha=alpha,
                linewidths=1.4, marker="D",
            )
            ax.scatter(
                ramp_dom["z_daily_peak_mw"], ramp_dom["z_daily_max_ramp_mw"],
                color=color, s=size, alpha=alpha, marker="o",
            )

        # Reference lines at z=0
        ax.axhline(0, color="gray", lw=0.7, alpha=0.35)
        ax.axvline(0, color="gray", lw=0.7, alpha=0.35)

        # Legend — cluster colors only (markers explained in title/subtitle)
        handles = [
            mpatches.Patch(color=CLUSTER_COLORS[lbl], label=lbl)
            for lbl in LABEL_ORDER[ba]
        ]
        ax.legend(handles=handles, loc="upper left", fontsize=10,
                  frameon=True, framealpha=0.9)

        ax.set_title(BA_DISPLAY[ba], fontsize=17, fontweight="bold")
        ax.set_xlabel("Peak Load (z-score)", fontsize=14)
        ax.set_ylabel("Max Ramp (z-score)", fontsize=14)
        ax.grid(alpha=0.25)

    plt.suptitle(
        "Cluster Profiles: Peak Load vs. Max Ramp\n"
        "Filled circle = ramp-dominant day  |  Hollow diamond = load-dominant day  |  Dashed = parity line",
        fontsize=13, fontweight="bold", y=1.02,
    )
    plt.tight_layout()
    outpath = FIG_DIR / "06_cluster_scatter.png"
    plt.savefig(outpath, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {outpath}")


# ---------------------------------------------------------------------------
# Figure 2: Seasonal composition stacked bar per cluster
# ---------------------------------------------------------------------------

def plot_cluster_composition(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, ba in zip(axes, BAS):
        sub    = df[df["balancing_authority"] == ba].copy()
        labels = LABEL_ORDER[ba]

        # Count days per (cluster_label, season)
        counts = (
            sub.groupby(["cluster_label", "season"])
            .size()
            .unstack(fill_value=0)
            .reindex(index=labels, fill_value=0)
        )
        # Add missing season columns so order is consistent
        for s in SEASON_ORDER:
            if s not in counts.columns:
                counts[s] = 0
        counts = counts[SEASON_ORDER]

        # Stacked bar
        bottoms = [0] * len(labels)
        for season in SEASON_ORDER:
            vals = counts[season].values
            bars = ax.bar(
                range(len(labels)), vals,
                bottom=bottoms,
                color=SEASON_COLORS[season],
                label=season,
                edgecolor="white", linewidth=0.6,
            )
            # Label counts inside bars (skip if too small)
            for i, (v, b) in enumerate(zip(vals, bottoms)):
                if v >= 8:
                    ax.text(i, b + v / 2, str(v),
                            ha="center", va="center", fontsize=10, fontweight="bold",
                            color="white")
            bottoms = [b + v for b, v in zip(bottoms, vals)]

        # Total day count above each bar
        for i, total in enumerate(counts.sum(axis=1)):
            ax.text(i, total + 1.5, f"n={int(total)}", ha="center", va="bottom",
                    fontsize=9, color="gray")

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=11, rotation=15, ha="right")
        ax.set_ylabel("Days", fontsize=13)
        ax.set_title(BA_DISPLAY[ba], fontsize=17, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

        if ba == BAS[0]:
            ax.legend(title="Season", loc="upper right", fontsize=10,
                      frameon=True, framealpha=0.9)

    plt.suptitle(
        "Cluster Seasonal Composition\nHow each regime maps to Summer / Shoulder / Winter",
        fontsize=13, fontweight="bold", y=1.02,
    )
    plt.tight_layout()
    outpath = FIG_DIR / "06_cluster_composition.png"
    plt.savefig(outpath, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {outpath}")


if __name__ == "__main__":
    df = pd.read_csv(CLUSTER_CSV)
    df["date"]   = pd.to_datetime(df["date"])
    df["season"] = df["date"].dt.month.map(SEASON_MAP)

    plot_cluster_scatter(df)
    plot_cluster_composition(df)
