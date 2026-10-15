"""
Module 7: Event Composite Analysis

For each BA, identifies independent extreme stress events using:
  1. Cluster membership: candidates must be in the extreme K-means cluster
     for the given BA and season. The (BA, season) -> cluster_int mapping
     is auto-derived from cluster_diagnostics.derive_extreme_clusters, so
     re-runs don't require manual updates.
  2. Minimum separation: events must be > MIN_SEPARATION_DAYS apart
     (keeps the highest-stress day from any overlapping episode).

Outputs (data/processed/event_composite/):
  event_windows.csv   — asymmetric window around each event
  event_composite.csv — mean + std of each z-component at each relative day
  event_onset.csv     — average day (relative to peak) each component crosses +1 SD
  event_recovery.csv  — days until stress_z drops below ONSET_THRESHOLD after each peak
"""

import pandas as pd
import numpy as np
from pathlib import Path

from src.config import DAILY_PARQUET_PATH  # noqa: F401  (kept for downstream tooling)
from src.cluster_diagnostics import derive_extreme_clusters

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

# Minimum calendar days between selected events. Events closer than this
# are treated as one episode; only the peak day is kept.
MIN_SEPARATION_DAYS = 14

# Minimum stress_z a day must reach to be an event candidate, applied after
# the cluster filter. Drops fringe cluster members whose features placed
# them in the extreme cluster but whose actual composite score is not
# operationally meaningful. Summer floor is higher because summer extreme
# events are structurally stronger.
STRESS_FLOOR = {
    "Summer":   2.0,
    "Winter":   1.0,
    "Shoulder": 1.0,
}

# Asymmetric analysis window around each event peak. The post window is
# truncated per-event if the next event's pre-window would overlap.
PRE_WINDOW_DAYS  = 7
POST_WINDOW_DAYS = 14

# Z-score level a component must reach to be considered "onset."
ONSET_THRESHOLD = 1.0

# The two sub-components of the stress index
Z_COLS = ["z_daily_peak_mw", "z_daily_max_ramp_mw"]

# Human-readable labels used in event_onset.csv
COMPONENT_LABELS = {
    "z_daily_peak_mw":     "Peak Load",
    "z_daily_max_ramp_mw": "Max Ramp",
}

CLUSTER_PARQUET_PATH = Path("data/processed/unsupervised/daily_with_clusters.parquet")
OUTPUT_DIR           = Path("data/processed/event_composite")


# ---------------------------------------------------------------------------
# Step 1: Select independent extreme events per BA
# ---------------------------------------------------------------------------

def select_events(candidates: pd.DataFrame) -> pd.DataFrame:
    """
    Returns selected extreme events with an event_rank column (1 = most extreme).
    candidates is pre-filtered to the extreme cluster for the given BA and season,
    and must already include a 'season' column.
    """
    candidates = candidates.sort_values("stress_z", ascending=False).copy()

    selected = []
    for _, row in candidates.iterrows():
        if not selected:
            selected.append(row)
            continue

        too_close = any(
            abs((row["date"] - s["date"]).days) <= MIN_SEPARATION_DAYS
            for s in selected
        )
        if not too_close:
            selected.append(row)

    if not selected:
        return pd.DataFrame()

    out = pd.DataFrame(selected).reset_index(drop=True)
    out["event_rank"] = range(1, len(out) + 1)
    return out


# ---------------------------------------------------------------------------
# Step 2: Extract the asymmetric window around each selected event
# ---------------------------------------------------------------------------

def extract_windows(ba_df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    events_sorted = events.sort_values("date").reset_index(drop=True)
    rows = []
    for i, ev in events_sorted.iterrows():
        if i + 1 < len(events_sorted):
            gap = (events_sorted.loc[i + 1, "date"] - ev["date"]).days
            max_right = min(POST_WINDOW_DAYS, gap - PRE_WINDOW_DAYS - 1)
        else:
            max_right = POST_WINDOW_DAYS

        truncated = max_right < POST_WINDOW_DAYS

        for rd in range(-PRE_WINDOW_DAYS, max_right + 1):
            target_date = ev["date"] + pd.Timedelta(days=rd)
            match = ba_df[ba_df["date"] == target_date]
            if match.empty:
                continue
            r = match.iloc[0]
            rows.append({
                "balancing_authority":       ev["balancing_authority"],
                "season":                    ev["season"],
                "event_rank":                ev["event_rank"],
                "event_date":                ev["date"].date(),
                "event_stress_z":            ev["stress_z"],
                "relative_day":              rd,
                "date":                      r["date"].date(),
                "z_daily_peak_mw":           r["z_daily_peak_mw"],
                "z_daily_max_ramp_mw":       r["z_daily_max_ramp_mw"],
                "stress_z":                  r["stress_z"],
                "recovery_window_days":      max_right,
                "recovery_window_truncated": truncated,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 3: Build composite trajectory
# ---------------------------------------------------------------------------

def build_composite(windows: pd.DataFrame) -> pd.DataFrame:
    agg = {}
    for col in Z_COLS + ["stress_z"]:
        agg[f"mean_{col}"] = (col, "mean")
        agg[f"std_{col}"]  = (col, "std")

    group_cols = ["balancing_authority", "season", "relative_day"]
    composite = windows.groupby(group_cols).agg(**agg).reset_index()
    composite["n_events"] = (
        windows.groupby(group_cols)["event_rank"].nunique().values
    )
    return composite


# ---------------------------------------------------------------------------
# Step 4: Onset timing
# ---------------------------------------------------------------------------

def compute_onset(windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ba, season, rank), grp in windows.groupby(
        ["balancing_authority", "season", "event_rank"]
    ):
        grp = grp.sort_values("relative_day")
        pre = grp[grp["relative_day"] <= 0]

        for col, label in COMPONENT_LABELS.items():
            crossed = pre[pre[col] >= ONSET_THRESHOLD]["relative_day"]
            onset = crossed.min() if not crossed.empty else np.nan
            rows.append({
                "balancing_authority": ba,
                "season":              season,
                "event_rank":          rank,
                "component":           label,
                "onset_relative_day":  onset,
            })

    onset_df = pd.DataFrame(rows)
    summary = (
        onset_df.groupby(["balancing_authority", "season", "component"])["onset_relative_day"]
        .agg(
            mean_onset="mean",
            median_onset="median",
            n_events_with_onset=lambda x: x.notna().sum(),
        )
        .reset_index()
    )
    summary["mean_onset"]   = summary["mean_onset"].round(1)
    summary["median_onset"] = summary["median_onset"].round(1)
    return summary


# ---------------------------------------------------------------------------
# Step 5: Per-event recovery time
# ---------------------------------------------------------------------------

def compute_recovery(windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ba, season, rank), grp in windows.groupby(
        ["balancing_authority", "season", "event_rank"]
    ):
        grp = grp.sort_values("relative_day")
        event_date    = grp["event_date"].iloc[0]
        peak_row      = grp[grp["relative_day"] == 0]
        peak_stress_z = float(peak_row["stress_z"].iloc[0]) if not peak_row.empty else np.nan
        max_right     = int(grp["recovery_window_days"].iloc[0])
        truncated     = bool(grp["recovery_window_truncated"].iloc[0])

        recovery_day = np.nan
        for _, row in grp[grp["relative_day"] > 0].iterrows():
            if row["stress_z"] < ONSET_THRESHOLD:
                recovery_day = int(row["relative_day"])
                break

        rows.append({
            "balancing_authority":       ba,
            "season":                    season,
            "event_rank":                rank,
            "event_date":                event_date,
            "peak_stress_z":             round(peak_stress_z, 3),
            "recovery_day":              recovery_day,
            "recovery_window_days":      max_right,
            "recovery_window_truncated": truncated,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(CLUSTER_PARQUET_PATH)
    df["date"] = pd.to_datetime(df["date"])

    if "season" not in df.columns:
        raise RuntimeError(
            "daily_with_clusters is missing the 'season' column. "
            "Re-run `make stress_daily` and `make unsupervised` to regenerate."
        )

    extreme_map = derive_extreme_clusters(df)
    print("Auto-derived extreme clusters per (BA, season):")
    for ba, season_map in extreme_map.items():
        print(f"  {ba}: {season_map}")

    all_windows = []
    all_events  = []

    for ba, ba_df in df.groupby("balancing_authority"):
        ba_seasons = extreme_map.get(ba, {})
        if not ba_seasons:
            print(f"[{ba}] No extreme clusters detected — skipping.")
            continue

        ba_events_list = []

        for season, extreme_cluster in ba_seasons.items():
            floor = STRESS_FLOOR.get(season, 0.0)
            candidates = ba_df[
                (ba_df["season"] == season) &
                (ba_df["cluster"] == extreme_cluster) &
                (ba_df["stress_z"] >= floor)
            ].copy()

            if candidates.empty:
                print(f"[{ba}] [{season}] No days in extreme cluster {extreme_cluster} above floor {floor}")
                continue

            events = select_events(candidates)
            if events.empty:
                print(f"[{ba}] [{season}] No independent events after separation filter")
                continue

            print(f"\n[{ba}] [{season}] {len(events)} events (cluster {extreme_cluster}, floor stress_z>={floor}):")
            for _, ev in events.iterrows():
                print(f"  Rank {int(ev['event_rank'])}: {ev['date'].date()}  stress_z={ev['stress_z']:.3f}")

            ba_events_list.append(events)

        if not ba_events_list:
            print(f"[{ba}] No events found in any extreme cluster.")
            continue

        ba_events = pd.concat(ba_events_list, ignore_index=True)
        windows   = extract_windows(ba_df, ba_events)
        all_windows.append(windows)
        all_events.append(
            ba_events[["balancing_authority", "season", "event_rank", "date", "stress_z"]]
        )

    if not all_windows:
        print("No events found. Exiting.")
        return

    windows_df = pd.concat(all_windows, ignore_index=True)
    events_df  = pd.concat(all_events,  ignore_index=True)

    windows_df.to_csv(OUTPUT_DIR / "event_windows.csv", index=False)
    print(f"\nWrote {OUTPUT_DIR}/event_windows.csv  ({len(windows_df)} rows)")

    composite_df = build_composite(windows_df)
    composite_df.to_csv(OUTPUT_DIR / "event_composite.csv", index=False)
    print(f"Wrote {OUTPUT_DIR}/event_composite.csv  ({len(composite_df)} rows)")

    onset_df = compute_onset(windows_df)
    onset_df.to_csv(OUTPUT_DIR / "event_onset.csv", index=False)
    print(f"Wrote {OUTPUT_DIR}/event_onset.csv  ({len(onset_df)} rows)")

    recovery_df = compute_recovery(windows_df)
    recovery_df.to_csv(OUTPUT_DIR / "event_recovery.csv", index=False)
    print(f"Wrote {OUTPUT_DIR}/event_recovery.csv  ({len(recovery_df)} rows)")

    print("\n--- Onset Summary ---")
    print(onset_df.to_string(index=False))

    print("\n--- Recovery Summary ---")
    print(recovery_df.to_string(index=False))


if __name__ == "__main__":
    main()
