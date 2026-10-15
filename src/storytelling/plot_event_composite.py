"""
Storytelling Module 5: Event Composite Trajectory and Recovery

Generates two figures into reports/figures/storytelling/05_event_composite/:

  05_composite_trajectory.png  — composite mean trajectory (day -7 to +14) per BA,
                                  with component lines, ±1 std shading, onset
                                  annotation lines, and threshold reference lines.

  05_event_recovery.png        — per-event post-peak stress_z trajectories, with
                                  recovery day markers and truncated-window callouts.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

COMPOSITE_PATH = Path("data/processed/event_composite/event_composite.csv")
ONSET_PATH     = Path("data/processed/event_composite/event_onset.csv")
WINDOWS_PATH   = Path("data/processed/event_composite/event_windows.csv")
RECOVERY_PATH  = Path("data/processed/event_composite/event_recovery.csv")

FIG_DIR = Path("reports/figures/storytelling/05_event_composite")
FIG_DIR.mkdir(parents=True, exist_ok=True)

RECOVERY_THRESHOLD = 1.0
STRESS_THRESHOLD   = 3.0

BA_DISPLAY   = {"CISO": "CAISO", "PJM": "PJM"}
BAS          = ["CISO", "PJM"]
COLOR_LOAD   = "tab:blue"
COLOR_RAMP   = "tab:orange"
COLOR_STRESS = "tab:red"
EVENT_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]


# ---------------------------------------------------------------------------
# Figure 1: Composite trajectory with onset annotations
# ---------------------------------------------------------------------------

def plot_composite_trajectory():
    composite = pd.read_csv(COMPOSITE_PATH)
    onset     = pd.read_csv(ONSET_PATH)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=False)

    for ax, ba in zip(axes, BAS):
        c = composite[
            (composite["balancing_authority"] == ba) & (composite["season"] == "Summer")
        ].sort_values("relative_day")
        o = onset[
            (onset["balancing_authority"] == ba) & (onset["season"] == "Summer")
        ]
        rd = c["relative_day"]

        # Composite stress with ±1 std shading
        ax.plot(rd, c["mean_stress_z"], color=COLOR_STRESS, lw=2.5, label="Stress index (z)")
        ax.fill_between(
            rd,
            c["mean_stress_z"] - c["std_stress_z"],
            c["mean_stress_z"] + c["std_stress_z"],
            color=COLOR_STRESS, alpha=0.12,
        )

        # Component mean lines
        ax.plot(rd, c["mean_z_daily_peak_mw"],     color=COLOR_LOAD, lw=1.8, ls="--",
                label="Peak load (z)")
        ax.plot(rd, c["mean_z_daily_max_ramp_mw"], color=COLOR_RAMP, lw=1.8, ls="--",
                label="Max ramp (z)")

        # Horizontal references — labeled directly, not via legend
        ax.axhline(0,                  color="gray",       ls="--", lw=0.8, alpha=0.45)
        ax.axhline(RECOVERY_THRESHOLD, color="gray",       ls=":",  lw=1.2, alpha=0.8)
        ax.axhline(STRESS_THRESHOLD,   color=COLOR_STRESS, ls=":",  lw=1.2, alpha=0.45)

        # Peak day and onset lines — labeled directly, not via legend
        ax.axvline(0, color="black", lw=1.5, alpha=0.7)

        load_row   = o[o["component"] == "Peak Load"].iloc[0]
        ramp_row   = o[o["component"] == "Max Ramp"].iloc[0]
        load_onset = load_row["mean_onset"]
        ramp_onset = ramp_row["mean_onset"]

        ax.axvline(load_onset, color=COLOR_LOAD, lw=1.4, ls="-.", alpha=0.85)
        ax.axvline(ramp_onset, color=COLOR_RAMP, lw=1.4, ls="-.", alpha=0.85)

        # --- Direct labels ---
        # get_yaxis_transform: x in axes [0,1], y in data units
        # get_xaxis_transform: x in data units, y in axes [0,1]
        yax = ax.get_yaxis_transform()
        xax = ax.get_xaxis_transform()

        # Threshold labels on right margin
        # Recovery threshold: below the line for CAISO (crowded above), above for PJM
        if ba == "CISO":
            ax.text(0.985, RECOVERY_THRESHOLD - 0.08, "Recovery\nthreshold",
                    transform=yax, ha="right", va="top", fontsize=8, color="gray")
        else:
            ax.text(0.985, RECOVERY_THRESHOLD + 0.08, "Recovery\nthreshold",
                    transform=yax, ha="right", va="bottom", fontsize=8, color="gray")
        ax.text(0.985, STRESS_THRESHOLD + 0.08, "Event\nthreshold",
                transform=yax, ha="right", va="bottom", fontsize=8,
                color=COLOR_STRESS, alpha=0.7)

        # Vertical line labels near top — staggered, with white text boxes
        label_box = dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none", alpha=0.85)
        ax.text(0.3, 0.97, "Peak", transform=xax,
                ha="center", va="top", fontsize=8, color="black", fontweight="bold")
        ax.text(load_onset, 0.97, f"Load onset\n(day {load_onset:+.1f})",
                transform=xax, ha="center", va="top", fontsize=8,
                color=COLOR_LOAD, style="italic", bbox=label_box)
        ax.text(ramp_onset, 0.84, f"Ramp onset\n(day {ramp_onset:+.1f})",
                transform=xax, ha="center", va="top", fontsize=8,
                color=COLOR_RAMP, style="italic", bbox=label_box)

        # n_events step-down note (PJM only) — bottom-right corner
        # Describes the gradual drop as truncated event windows end
        post = c[c["relative_day"] > 0]
        if post["n_events"].nunique() > 1:
            max_n      = int(post["n_events"].max())
            first_drop = int(post[post["n_events"] < max_n]["relative_day"].min())
            min_n      = int(post["n_events"].min())
            min_n_day  = int(post[post["n_events"] == min_n]["relative_day"].min())
            ax.text(0.98, 0.04,
                    f"n={max_n} events through day +{first_drop - 1}; "
                    f"steps down to n={min_n} by day +{min_n_day}\n"
                    f"(shading requires n≥2; disappears at day +{min_n_day})",
                    transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=8, color="gray", style="italic")

        ax.set_title(BA_DISPLAY[ba], fontsize=17, fontweight="bold")
        ax.set_xlabel("Days relative to stress peak", fontsize=16)
        ax.set_ylabel("Z-score", fontsize=16)
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right", fontsize=10, frameon=True, framealpha=0.9)

    plt.suptitle(
        "Composite Extreme Event Trajectory — Summer Events  |  Shading = ±1 SD across events",
        fontsize=14, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    outpath = FIG_DIR / "05_composite_trajectory.png"
    plt.savefig(outpath, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {outpath}")


# ---------------------------------------------------------------------------
# Figure 2: Per-event post-peak recovery trajectories
# ---------------------------------------------------------------------------

def plot_event_recovery():
    windows  = pd.read_csv(WINDOWS_PATH)
    recovery = pd.read_csv(RECOVERY_PATH)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for ax, ba in zip(axes, BAS):
        w = windows[windows["balancing_authority"] == ba]
        r = recovery[recovery["balancing_authority"] == ba].sort_values(
            "peak_stress_z", ascending=False
        ).reset_index(drop=True)

        # Reference lines
        ax.axhline(
            RECOVERY_THRESHOLD, color="gray", ls="--", lw=1.5, alpha=0.8,
            label=f"Recovery threshold (z={RECOVERY_THRESHOLD})",
        )
        ax.axhline(0, color="gray", ls="--", lw=0.8, alpha=0.4)

        for idx, ev_row in r.iterrows():
            rank      = ev_row["event_rank"]
            ev_date   = ev_row["event_date"]
            peak_z    = ev_row["peak_stress_z"]
            rec_day   = ev_row["recovery_day"]
            truncated = bool(ev_row["recovery_window_truncated"])
            max_right = int(ev_row["recovery_window_days"])

            ev_win = (
                w[(w["event_rank"] == rank) & (w["relative_day"] >= 0)]
                .sort_values("relative_day")
            )

            color = EVENT_COLORS[idx % len(EVENT_COLORS)]
            ls    = "--" if truncated else "-"
            label = f"{ev_date}  (peak z={peak_z:.1f})"
            if truncated:
                label += f"  [window ={max_right}d]"

            ax.plot(ev_win["relative_day"], ev_win["stress_z"],
                    color=color, lw=2.0, ls=ls, label=label)

            # Recovery day marker
            if not (isinstance(rec_day, float) and np.isnan(rec_day)):
                rec_day = int(rec_day)
                rec_row = ev_win[ev_win["relative_day"] == rec_day]
                if not rec_row.empty:
                    y_val = rec_row["stress_z"].values[0]
                    ax.scatter(rec_day, y_val, color=color, s=80, zorder=5, marker="o")
                    ax.annotate(
                        f"+{rec_day}d",
                        xy=(rec_day, y_val),
                        xytext=(rec_day + 0.4, y_val + 0.25),
                        fontsize=9, color=color, fontweight="bold",
                    )

            # Mark truncation point with an 'x'
            if truncated:
                last_row = ev_win.iloc[-1]
                ax.scatter(
                    last_row["relative_day"], last_row["stress_z"],
                    color=color, s=80, zorder=5, marker="x", linewidths=2,
                )

        ax.set_title(BA_DISPLAY[ba], fontsize=17, fontweight="bold")
        ax.set_xlabel("Days after stress peak", fontsize=16)
        ax.set_ylabel("Stress Index (z)", fontsize=16)
        ax.set_xlim(left=0)
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right", fontsize=10, frameon=True, framealpha=0.9)

    plt.suptitle(
        "Post-Peak Stress Recovery by Event — Summer Events\n"
        "Circles = recovery day  |  Dashed lines / × = window truncated by next event",
        fontsize=13, fontweight="bold", y=1.02,
    )
    plt.tight_layout()
    outpath = FIG_DIR / "05_event_recovery.png"
    plt.savefig(outpath, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {outpath}")


if __name__ == "__main__":
    plot_composite_trajectory()
    plot_event_recovery()
