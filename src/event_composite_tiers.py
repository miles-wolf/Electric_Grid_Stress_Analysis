"""
Multi-tier event composite analysis — Elevated + Extreme.

Runs the same selection / windowing / aggregation logic as event_composite.py
across both the Elevated and Extreme stress clusters, tagging every output row
with a stress_tier column so Power BI can show them side-by-side or toggle.

Key difference from event_composite.py:
  - No season-concentration filter on cluster selection. Events are drawn from
    whichever cluster carries the target label, then split by their actual
    calendar season. This surfaces PJM winter events that live in the Elevated
    cluster (46 % winter / 46 % summer) and the handful of PJM winter days
    that landed in the Extreme cluster.
  - Stress floors are lower for Elevated to avoid over-filtering that tier.

Outputs (data/processed/event_composite/):
  event_onset_tiers.csv
  event_composite_tiers.csv
  event_windows_tiers.csv
  event_recovery_tiers.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

from src.cluster_diagnostics import auto_label_clusters
from src.event_composite import (
    select_events,
    extract_windows,
    build_composite,
    compute_onset,
    compute_recovery,
)

CLUSTER_PARQUET = Path("data/processed/unsupervised/daily_with_clusters.parquet")
OUTPUT_DIR      = Path("data/processed/event_composite")

TIERS = ["Elevated", "Extreme"]

# Minimum stress_z to be an event candidate, by tier and season.
# Extreme floors match event_composite.py; Elevated floors are intentionally
# permissive since the cluster mean is already modest.
STRESS_FLOOR = {
    "Extreme":  {"Summer": 2.0, "Winter": 1.0, "Shoulder": 1.0},
    "Elevated": {"Summer": 0.5, "Winter": 0.0, "Shoulder": 0.0},
}

# Seasons that need at least this many candidate days to attempt event selection
MIN_CANDIDATE_DAYS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def label_to_cluster_map(df: pd.DataFrame) -> dict:
    """Returns {ba: {label: cluster_int}} — inverse of auto_label_clusters."""
    fwd = auto_label_clusters(df)   # {ba: {cluster_int: label}}
    return {
        ba: {label: cid for cid, label in ba_map.items()}
        for ba, ba_map in fwd.items()
    }


def run_tier(df: pd.DataFrame, tier: str) -> tuple:
    """
    Identify events for one stress tier across all BAs and seasons.
    Returns (windows_list, events_list) — each a list of DataFrames.
    """
    inv_map = label_to_cluster_map(df)
    all_windows, all_events = [], []

    for ba, ba_df in df.groupby("balancing_authority"):
        tier_cluster = inv_map.get(ba, {}).get(tier)
        if tier_cluster is None:
            print(f"[{ba}] [{tier}] No cluster labeled '{tier}' — skipping.")
            continue

        tier_days = ba_df[ba_df["cluster"] == tier_cluster]
        ba_events_list = []

        for season in sorted(tier_days["season"].unique()):
            floor      = STRESS_FLOOR[tier].get(season, 0.0)
            candidates = tier_days[
                (tier_days["season"] == season) &
                (tier_days["stress_z"] >= floor)
            ].copy()

            if len(candidates) < MIN_CANDIDATE_DAYS:
                print(f"[{ba}] [{tier}] [{season}] Only {len(candidates)} candidates "
                      f"(need {MIN_CANDIDATE_DAYS}) — skipping.")
                continue

            events = select_events(candidates)
            if events.empty:
                print(f"[{ba}] [{tier}] [{season}] No independent events after separation filter.")
                continue

            print(f"\n[{ba}] [{tier}] [{season}] {len(events)} events "
                  f"(cluster {tier_cluster}, floor z>={floor}):")
            for _, ev in events.iterrows():
                print(f"  Rank {int(ev['event_rank'])}: {ev['date'].date()}  "
                      f"stress_z={ev['stress_z']:.3f}")

            ba_events_list.append(events)

        if not ba_events_list:
            print(f"[{ba}] [{tier}] No events found in any season.")
            continue

        ba_events = pd.concat(ba_events_list, ignore_index=True)
        windows   = extract_windows(ba_df, ba_events)
        all_windows.append(windows)
        all_events.append(
            ba_events[["balancing_authority", "season", "event_rank", "date", "stress_z"]]
        )

    return all_windows, all_events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(CLUSTER_PARQUET)
    df["date"] = pd.to_datetime(df["date"])

    if "season" not in df.columns:
        raise RuntimeError(
            "daily_with_clusters is missing the 'season' column. "
            "Re-run `make stress_daily` and `make unsupervised`."
        )

    all_windows_frames, all_events_frames = [], []

    for tier in TIERS:
        print(f"\n{'='*60}")
        print(f"  Processing tier: {tier}")
        print(f"{'='*60}")
        tier_windows, tier_events = run_tier(df, tier)

        for w in tier_windows:
            w["stress_tier"] = tier
        for e in tier_events:
            e["stress_tier"] = tier

        all_windows_frames.extend(tier_windows)
        all_events_frames.extend(tier_events)

    if not all_windows_frames:
        print("No events found across any tier. Exiting.")
        return

    windows_df = pd.concat(all_windows_frames, ignore_index=True)
    events_df  = pd.concat(all_events_frames,  ignore_index=True)

    # Build per-tier composite, onset, and recovery so the groupby keys stay clean
    composites, onsets, recoveries = [], [], []

    for tier in TIERS:
        tier_w = windows_df[windows_df["stress_tier"] == tier]
        if tier_w.empty:
            continue

        c = build_composite(tier_w)
        c["stress_tier"] = tier
        composites.append(c)

        o = compute_onset(tier_w)
        o["stress_tier"] = tier
        onsets.append(o)

        r = compute_recovery(tier_w)
        r["stress_tier"] = tier
        recoveries.append(r)

    composite_df = pd.concat(composites, ignore_index=True)
    onset_df     = pd.concat(onsets,     ignore_index=True)
    recovery_df  = pd.concat(recoveries, ignore_index=True)

    # Save
    windows_df.to_csv(OUTPUT_DIR / "event_windows_tiers.csv",    index=False)
    composite_df.to_csv(OUTPUT_DIR / "event_composite_tiers.csv", index=False)
    onset_df.to_csv(OUTPUT_DIR    / "event_onset_tiers.csv",      index=False)
    recovery_df.to_csv(OUTPUT_DIR / "event_recovery_tiers.csv",   index=False)

    print(f"\nWrote event_windows_tiers.csv    ({len(windows_df)} rows)")
    print(f"Wrote event_composite_tiers.csv  ({len(composite_df)} rows)")
    print(f"Wrote event_onset_tiers.csv      ({len(onset_df)} rows)")
    print(f"Wrote event_recovery_tiers.csv   ({len(recovery_df)} rows)")

    print("\n--- Onset Summary ---")
    print(onset_df.sort_values(
        ["balancing_authority", "stress_tier", "season", "component"]
    ).to_string(index=False))


if __name__ == "__main__":
    main()
