import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

# -----------------------------
# Paths
# -----------------------------
DATA_PATH = Path("data/processed/unsupervised/daily_with_clusters.parquet")
FIG_DIR = Path("reports/figures/storytelling/04_temporal_trajectories")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Columns
# -----------------------------
DATE_COL = "date"
BA_COL = "balancing_authority"
LOAD_COL = "z_daily_peak_mw"
RAMP_COL = "z_daily_max_ramp_mw"
FRAG_COL = "fragility_z"
CLUSTER_COL = "cluster"

# -----------------------------
# Parameters
# -----------------------------
N_EVENTS = 3
WINDOW_DAYS = 7       # ± days around each event
MIN_SEPARATION = 7    # minimum separation between event centers


def select_top_events(df_ba: pd.DataFrame):
    """
    Select top N_EVENTS fragility days with temporal separation.
    """
    df = df_ba.sort_values(FRAG_COL, ascending=False).copy()
    selected = []

    for _, row in df.iterrows():
        date = row[DATE_COL]

        if all(abs((date - d).days) > MIN_SEPARATION for d in selected):
            selected.append(date)

        if len(selected) == N_EVENTS:
            break

    return selected


def plot_trajectory_combined(df_win: pd.DataFrame, ba: str, event_id: int):
    """
    Combined plot with 2 sections:
      (top)  Load (left y) + Ramp (right y)
      (bottom) Cluster ID (left y) + Fragility (right y)
    """
    # Display CAISO instead of CISO
    display_name = "CAISO" if ba == "CISO" else ba
    
    fig, axes = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True,
        gridspec_kw={"height_ratios": [1, 1]}
    )

    # -------------------------
    # TOP: Load (left) + Ramp (right)
    # -------------------------
    ax_top = axes[0]
    ax_top_r = ax_top.twinx()

    l1, = ax_top.plot(df_win[DATE_COL], df_win[LOAD_COL], color="tab:blue", label="Peak Load (z)")
    l2, = ax_top_r.plot(df_win[DATE_COL], df_win[RAMP_COL], color="tab:orange", label="Max Ramp (z)")

    ax_top.set_ylabel("Peak Load (z)", fontsize=16)
    ax_top_r.set_ylabel("Max Ramp (z)", fontsize=16)
    ax_top.grid(alpha=0.3)

    # One combined legend for top panel - positioned dynamically to avoid data
    ax_top.legend(handles=[l1, l2], loc="best", frameon=True, framealpha=0.9, fontsize=13)

    # -------------------------
    # BOTTOM: Cluster (left) + Fragility (right)
    # -------------------------
    ax_bot = axes[1]
    ax_bot_r = ax_bot.twinx()

    l3 = ax_bot.step(
        df_win[DATE_COL],
        df_win[CLUSTER_COL],
        where="post",
        color="tab:green",
        label="Cluster ID"
    )[0]

    l4, = ax_bot_r.plot(
        df_win[DATE_COL],
        df_win[FRAG_COL],
        color="tab:red",
        label="Fragility (z)"
    )
    ax_bot_r.axhline(0, color="gray", linestyle="--", alpha=0.6)

    ax_bot.set_ylabel("Cluster ID", fontsize=16)
    ax_bot_r.set_ylabel("Fragility (z)", fontsize=16)
    ax_bot.grid(alpha=0.3)
    ax_bot.set_xlabel("Date", fontsize=16)

    # Make cluster ticks integers (helps readability)
    ax_bot.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    # One combined legend for bottom panel - positioned dynamically to avoid data
    ax_bot.legend(handles=[l3, l4], loc="best", frameon=True, framealpha=0.9, fontsize=13)

    # -------------------------
    # Shared x formatting (2-day tick spacing, rotated labels)
    # -------------------------
    ax_bot.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d-%y'))
    plt.setp(ax_bot.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()

    outpath = FIG_DIR / f"04_{ba.lower()}_event{event_id + 1}_combined.png"
    plt.savefig(outpath, dpi=200)
    plt.close()
    print(f"Wrote {outpath}")


if __name__ == "__main__":
    df = pd.read_parquet(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    for ba in sorted(df[BA_COL].unique()):
        df_ba = df[df[BA_COL] == ba].sort_values(DATE_COL)

        event_dates = select_top_events(df_ba)
        print(f"{ba}: selected events at {[d.date() for d in event_dates]}")

        for i, center_date in enumerate(event_dates):
            start = center_date - pd.Timedelta(days=WINDOW_DAYS)
            end = center_date + pd.Timedelta(days=WINDOW_DAYS)

            df_win = df_ba[
                (df_ba[DATE_COL] >= start) &
                (df_ba[DATE_COL] <= end)
            ]

            plot_trajectory_combined(df_win, ba, i)
