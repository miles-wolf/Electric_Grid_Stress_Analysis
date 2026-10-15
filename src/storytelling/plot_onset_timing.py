"""
Page 3 — Section 1: Event Onset Lead Time
Horizontal grouped bar chart showing how many days before the stress peak
each component (Peak Load, Max Ramp) crosses the onset threshold, broken
out by regime (CISO Summer / PJM Summer / PJM Winter) and tier (Extreme /
Elevated).

Output: reports/figures/storytelling/page3/S1_onset_timing.png
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

DATA_PATH = Path("data/processed/dashboard/page3_data.csv")
FIG_DIR   = Path("reports/figures/storytelling/page3")
FIG_DIR.mkdir(parents=True, exist_ok=True)

COLOR_LOAD = "#2C7BB6"
COLOR_RAMP = "#E07B39"

# Row order (top → bottom on chart = most extreme regime first)
ROW_ORDER = [
    ("CISO", "Summer", "Extreme"),
    ("CISO", "Summer", "Elevated"),
    ("PJM",  "Summer", "Extreme"),
    ("PJM",  "Summer", "Elevated"),
    ("PJM",  "Winter", "Extreme"),
    ("PJM",  "Winter", "Elevated"),
]

ROW_LABELS = {
    ("CISO", "Summer", "Extreme"):  "CAISO Summer — Extreme",
    ("CISO", "Summer", "Elevated"): "CAISO Summer — Elevated",
    ("PJM",  "Summer", "Extreme"):  "PJM Summer — Extreme",
    ("PJM",  "Summer", "Elevated"): "PJM Summer — Elevated",
    ("PJM",  "Winter", "Extreme"):  "PJM Winter — Extreme",
    ("PJM",  "Winter", "Elevated"): "PJM Winter — Elevated",
}

# Alpha for Elevated bars (slightly lighter to distinguish from Extreme)
TIER_ALPHA = {"Extreme": 1.0, "Elevated": 0.62}


def main():
    df = pd.read_csv(DATA_PATH)
    onset = df[df["record_type"] == "onset"].copy()
    onset["lead_days"] = onset["mean_onset_days"].abs()
    onset = onset[onset["season"].isin(["Summer", "Winter"])]

    # Index for quick lookup
    idx = onset.set_index(
        ["balancing_authority", "season", "stress_tier", "component"]
    )["lead_days"].to_dict()
    n_idx = onset.set_index(
        ["balancing_authority", "season", "stress_tier", "component"]
    )["n_events_onset"].to_dict()

    fig, ax = plt.subplots(figsize=(11, 7))

    bar_h     = 0.32
    group_gap = 0.25   # extra vertical space between regime groups
    n_rows    = len(ROW_ORDER)

    # Build y-positions with a gap after every 2 rows (between regime groups)
    y_positions = []
    y = 0.0
    for i, row in enumerate(ROW_ORDER):
        y_positions.append(y)
        y -= (bar_h * 2 + 0.08)   # two bars per row + internal gap
        if i % 2 == 1:             # after each Elevated row, add regime gap
            y -= group_gap

    for i, (ba, season, tier) in enumerate(ROW_ORDER):
        y_base  = y_positions[i]
        alpha   = TIER_ALPHA[tier]

        load_val = idx.get((ba, season, tier, "Peak Load"), 0)
        ramp_val = idx.get((ba, season, tier, "Max Ramp"),  0)
        load_n   = int(n_idx.get((ba, season, tier, "Peak Load"), 0))
        ramp_n   = int(n_idx.get((ba, season, tier, "Max Ramp"),  0))

        # Peak Load bar (upper)
        ax.barh(y_base + bar_h / 2, load_val, height=bar_h,
                color=COLOR_LOAD, alpha=alpha, zorder=3)
        if load_val > 0:
            ax.text(load_val + 0.1, y_base + bar_h / 2,
                    f"{load_val:.1f}d  (n={load_n})",
                    va="center", ha="left", fontsize=8.5,
                    color=COLOR_LOAD, alpha=min(alpha + 0.2, 1.0))

        # Max Ramp bar (lower)
        ax.barh(y_base - bar_h / 2, ramp_val, height=bar_h,
                color=COLOR_RAMP, alpha=alpha, zorder=3)
        if ramp_val > 0:
            ax.text(ramp_val + 0.1, y_base - bar_h / 2,
                    f"{ramp_val:.1f}d  (n={ramp_n})",
                    va="center", ha="left", fontsize=8.5,
                    color=COLOR_RAMP, alpha=min(alpha + 0.2, 1.0))

    # Y-axis labels at the mid-point of each row pair
    row_mid_y = []
    for i, (ba, season, tier) in enumerate(ROW_ORDER):
        row_mid_y.append(y_positions[i])

    ax.set_yticks(row_mid_y)
    ax.set_yticklabels(
        [ROW_LABELS[r] for r in ROW_ORDER],
        fontsize=11,
    )

    # Tier label annotation on the right margin
    for i, (ba, season, tier) in enumerate(ROW_ORDER):
        ax.text(8.6, y_positions[i], tier,
                va="center", ha="left", fontsize=8,
                color="#666666", style="italic")

    # Regime group dividers
    divider_ys = []
    for i in range(1, len(ROW_ORDER)):
        if i % 2 == 0:
            mid = (y_positions[i] + y_positions[i - 1]) / 2 - 0.1
            divider_ys.append(mid)

    for dy in divider_ys:
        ax.axhline(dy, color="#cccccc", lw=0.9, ls="--", zorder=1)

    # Reference line at 0 and x-axis formatting
    ax.axvline(0, color="black", lw=0.8, alpha=0.5)
    ax.set_xlim(0, 8.8)
    ax.set_xlabel("Days of lead time before stress peak", fontsize=12)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.25, zorder=0)
    ax.set_axisbelow(True)

    # Legend
    patches = [
        mpatches.Patch(color=COLOR_LOAD, label="Peak Load onset"),
        mpatches.Patch(color=COLOR_RAMP, label="Max Ramp onset"),
        mpatches.Patch(color="gray", alpha=1.0,  label="Extreme tier"),
        mpatches.Patch(color="gray", alpha=0.55, label="Elevated tier"),
    ]
    ax.legend(handles=patches, fontsize=10, loc="lower right",
              framealpha=0.9, ncol=2)

    ax.set_title(
        "Event Onset Lead Time by Regime and Stress Tier\n"
        "How many days before the stress peak each component crosses the onset threshold (z ≥ 1.0)",
        fontsize=13, fontweight="bold",
    )

    plt.tight_layout()
    out = FIG_DIR / "S1_onset_timing.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
