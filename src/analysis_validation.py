"""
Validation Analysis — Electric Grid Demand Stress Analysis
Tests whether CAISO's demand stress is systematically ramp-driven
or an artifact of a single outlier day.

Tests:
  B — Feature contribution on high-stress CAISO days
  C — Cluster membership split by BA
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

DATA_PATH = Path("data/processed/unsupervised/daily_with_clusters.csv")
FIG_DIR = Path("reports/figures/validation")

COMPONENT_LABELS = {
    "z_daily_peak_mw": "Peak Load",
    "z_daily_max_ramp_mw": "Max Ramp",
}

# The two components that make up stress_z
COMPONENTS = [
    "z_daily_peak_mw",
    "z_daily_max_ramp_mw",
]

# Threshold for "high stress" days (1 standard deviation above mean)
HIGH_STRESS_THRESHOLD = 1.0


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    print(f"Loaded {len(df)} rows | BAs: {sorted(df['balancing_authority'].unique())}\n")
    return df


def _savefig(filename: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / filename
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote figure: {path}")


# ─────────────────────────────────────────────
# TEST B: Feature contribution by stress tier
# ─────────────────────────────────────────────
def test_b_contributions(df: pd.DataFrame) -> None:
    print("=" * 55)
    print("TEST B — Feature contribution by stress tier, CAISO vs PJM")
    print(f"         High = stress_z > {HIGH_STRESS_THRESHOLD}")
    print("=" * 55)
    print("Confirms that CAISO high-stress days are ramp-driven")
    print("while PJM high-stress days are peak-load-driven.\n")

    bas = sorted(df["balancing_authority"].unique())
    contrib_data = {}

    for ba in bas:
        subset = df[df["balancing_authority"] == ba]
        high = subset[subset["stress_z"] > HIGH_STRESS_THRESHOLD]
        low  = subset[subset["stress_z"] <= HIGH_STRESS_THRESHOLD]
        display_name = "CAISO" if ba == "CISO" else ba

        for tier_label, tier_df in [(f"{display_name} high (n={len(high)})", high),
                                    (f"{display_name} low  (n={len(low)})",  low)]:
            means = tier_df[COMPONENTS].mean()
            total = means.abs().sum()
            contrib_data[tier_label] = means
            print(f"  {tier_label}")
            for col in COMPONENTS:
                pct = (means[col] / total * 100) if total != 0 else 0
                print(f"    {COMPONENT_LABELS[col]:<20} mean z = {means[col]:+.3f}  ({pct:.1f}%)")
            print(f"    {'stress_z (mean)':<20} mean   = {tier_df['stress_z'].mean():.3f}")
            print()

    # Plot — one bar group per tier
    x = np.arange(len(COMPONENTS))
    width = 0.2
    labels = [COMPONENT_LABELS[c] for c in COMPONENTS]

    _, ax = plt.subplots(figsize=(11, 5))
    for i, (label, means) in enumerate(contrib_data.items()):
        vals = [means[c] for c in COMPONENTS]
        ax.bar(x + i * width, vals, width, label=label, alpha=0.8)

    ax.set_xticks(x + width * (len(contrib_data) - 1) / 2)
    ax.set_xticklabels(labels, fontsize=16)
    ax.set_ylabel("Mean z-score contribution", fontsize=16)
    ax.axhline(0, color="gray", linestyle="--", linewidth=1, alpha=0.5)
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    _savefig("test_b_contributions.png")


# ─────────────────────────────────────────────
# TEST C: Cluster membership by BA
# ─────────────────────────────────────────────
def test_c_cluster_membership(df: pd.DataFrame) -> None:
    print("=" * 55)
    print("TEST C — Cluster membership split by BA")
    print("=" * 55)
    print("Shows whether clusters are BA-specific or mixed.\n")

    counts = (
        df.groupby(["balancing_authority", "cluster"])
        .size()
        .unstack(fill_value=0)
    )
    print("  Day counts per cluster:\n")
    print(counts.to_string())
    print()

    frag_means = (
        df.groupby(["balancing_authority", "cluster"])["stress_z"]
        .mean().unstack().round(3)
    )
    print("  Mean stress_z per cluster:\n")
    print(frag_means.to_string())
    print()

    ramp_means = (
        df.groupby(["balancing_authority", "cluster"])["z_daily_max_ramp_mw"]
        .mean().unstack().round(3)
    )
    print("  Mean z_daily_max_ramp_mw per cluster:\n")
    print(ramp_means.to_string())
    print()

    load_means = (
        df.groupby(["balancing_authority", "cluster"])["z_daily_peak_mw"]
        .mean().unstack().round(3)
    )
    print("  Mean z_daily_peak_mw per cluster:\n")
    print(load_means.to_string())
    print()

    # Plot — grouped bar of day counts per cluster, split by BA
    bas = sorted(df["balancing_authority"].unique())
    clusters = sorted(df["cluster"].unique())
    x = np.arange(len(clusters))
    width = 0.35

    _, ax = plt.subplots(figsize=(9, 5))
    for i, ba in enumerate(bas):
        display_name = "CAISO" if ba == "CISO" else ba
        vals = np.array([counts.loc[ba, c] if c in counts.columns else 0 for c in clusters])
        ax.bar(x + i * width, vals, width, label=display_name, alpha=0.8)

    ax.set_xticks(x + width / 2)
    ax.set_xticklabels([f"Cluster {c}" for c in clusters], fontsize=16)
    ax.set_ylabel("Number of days", fontsize=16)
    ax.legend(fontsize=14)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    _savefig("test_c_cluster_membership.png")


def main() -> None:
    df = load_data()
    test_b_contributions(df)
    test_c_cluster_membership(df)
    print("Validation complete.")


if __name__ == "__main__":
    main()
