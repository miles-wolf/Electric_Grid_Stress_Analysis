"""
Scratch script — NOT part of the pipeline.

Tests a conditional contribution fragility index variant against the current
formulation. Duration component (z_pct_hours_near_peak) only contributes when
z_daily_peak_mw >= PEAK_THRESHOLD, otherwise it is zeroed out.

Run from project root:
    python scratch_fragility_variants.py

Nothing is written to the processed data folders. All output is printed.
"""

import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_PATH = "data/processed/stress/daily_stress_pjm_ciso_2025.parquet"

# Threshold on z_daily_peak_mw below which duration does not contribute.
# Days with z_daily_peak_mw < this value have z_pct_hours_near_peak zeroed out.
PEAK_THRESHOLD = 0.5

TOP_N = 10       # top N fragile days to compare
K = 4            # clusters for the quick re-run


# ---------------------------------------------------------------------------
# Load data and compute variant
# ---------------------------------------------------------------------------

df = pd.read_parquet(DATA_PATH)
df["date"] = pd.to_datetime(df["date"])

# Current formulation (additive, no interaction)
# fragility_z already exists in the data — we keep it for comparison

# Conditional variant: duration only counts when peak is elevated
df["pct_contribution"] = df["z_pct_hours_near_peak"].where(
    df["z_daily_peak_mw"] >= PEAK_THRESHOLD, other=0.0
)
df["fragility_z_conditional"] = (
    df["z_daily_peak_mw"]
    + df["z_daily_max_ramp_mw"]
    + df["pct_contribution"]
)

# Re-normalise conditional score to [0,1] per BA for easy comparison
def minmax(s: pd.Series) -> pd.Series:
    smin, smax = s.min(), s.max()
    return (s - smin) / (smax - smin) if smax != smin else pd.Series(np.nan, index=s.index)

df["fragility_01_conditional"] = df.groupby("balancing_authority")["fragility_z_conditional"].transform(minmax)


# ---------------------------------------------------------------------------
# 1. How many days are actually affected by the change?
# ---------------------------------------------------------------------------

print("=" * 65)
print("1. DAYS AFFECTED BY CONDITIONAL RULE")
print("=" * 65)

affected = df[df["z_daily_peak_mw"] < PEAK_THRESHOLD].copy()
affected["delta_fragility_z"] = (
    affected["fragility_z_conditional"] - affected["fragility_z"]
)

for ba, grp in affected.groupby("balancing_authority"):
    pct = len(grp) / len(df[df["balancing_authority"] == ba]) * 100
    print(f"\n{ba}: {len(grp)} days affected ({pct:.1f}% of year)")
    print(f"  Mean fragility_z change on affected days: {grp['delta_fragility_z'].mean():.3f}")
    print(f"  Max fragility_z change on affected days:  {grp['delta_fragility_z'].max():.3f}")
    print(f"  Min fragility_z change on affected days:  {grp['delta_fragility_z'].min():.3f}")


# ---------------------------------------------------------------------------
# 2. Rank correlation — does the ordering shift substantially?
# ---------------------------------------------------------------------------

print("\n" + "=" * 65)
print("2. RANK CORRELATION (Spearman) — current vs conditional")
print("=" * 65)

for ba, grp in df.groupby("balancing_authority"):
    r, p = spearmanr(grp["fragility_z"], grp["fragility_z_conditional"])
    print(f"\n{ba}: r = {r:.4f}  (p = {p:.2e})")
    if r > 0.99:
        print("  -> Rank ordering nearly identical")
    elif r > 0.95:
        print("  -> Minor rank shifts")
    else:
        print("  -> Substantial rank reordering")


# ---------------------------------------------------------------------------
# 3. Top N fragile days — do they change?
# ---------------------------------------------------------------------------

print("\n" + "=" * 65)
print(f"3. TOP {TOP_N} FRAGILE DAYS — current vs conditional")
print("=" * 65)

for ba, grp in df.groupby("balancing_authority"):
    top_current = (
        grp.nlargest(TOP_N, "fragility_z")[["date", "fragility_z", "z_daily_peak_mw", "z_pct_hours_near_peak"]]
        .assign(date=lambda x: x["date"].dt.date)
    )
    top_conditional = (
        grp.nlargest(TOP_N, "fragility_z_conditional")[["date", "fragility_z_conditional", "z_daily_peak_mw", "z_pct_hours_near_peak"]]
        .assign(date=lambda x: x["date"].dt.date)
    )

    current_dates = set(top_current["date"].astype(str))
    conditional_dates = set(top_conditional["date"].astype(str))
    added   = conditional_dates - current_dates
    removed = current_dates - conditional_dates

    print(f"\n{ba}:")
    print(f"  Days in common:  {len(current_dates & conditional_dates)}/{TOP_N}")
    if removed:
        print(f"  Dropped from top {TOP_N}: {sorted(removed)}")
    if added:
        print(f"  Added to top {TOP_N}:   {sorted(added)}")

    # Show side-by-side for any differences
    if added or removed:
        print(f"\n  Current top {TOP_N}:")
        for _, r in top_current.iterrows():
            marker = " <-- DROPPED" if str(r["date"]) in removed else ""
            print(f"    {r['date']}  fz={r['fragility_z']:.3f}  z_peak={r['z_daily_peak_mw']:.2f}  z_pct={r['z_pct_hours_near_peak']:.2f}{marker}")
        print(f"\n  Conditional top {TOP_N}:")
        for _, r in top_conditional.iterrows():
            marker = " <-- NEW" if str(r["date"]) in added else ""
            print(f"    {r['date']}  fz={r['fragility_z_conditional']:.3f}  z_peak={r['z_daily_peak_mw']:.2f}  z_pct={r['z_pct_hours_near_peak']:.2f}{marker}")
    else:
        print(f"  Top {TOP_N} days identical under both formulations.")


# ---------------------------------------------------------------------------
# 4. Quick K-means re-run on conditional scores — do cluster characters change?
# ---------------------------------------------------------------------------

print("\n" + "=" * 65)
print("4. CLUSTER CHARACTER — current vs conditional fragility_z")
print("=" * 65)

# We only re-score on the fragility dimension — use same feature matrix
# as the original pipeline but swap fragility_z for fragility_z_conditional
FEATURE_COLS = [
    "daily_peak_mw", "daily_min_mw", "daily_range_mw",
    "daily_max_ramp_mw", "daily_ramp_std", "pct_hours_near_peak",
    "z_daily_peak_mw", "z_daily_max_ramp_mw", "z_pct_hours_near_peak",
]

for ba, grp in df.groupby("balancing_authority"):
    grp = grp.copy()

    # Original clusters (already in data if daily_with_clusters was loaded,
    # but we re-run here on the original feature set for a clean baseline)
    X_orig = grp[FEATURE_COLS + ["fragility_z"]].values
    X_cond = grp[FEATURE_COLS + ["fragility_z_conditional"]].values

    scaler_orig = StandardScaler().fit(X_orig)
    scaler_cond = StandardScaler().fit(X_cond)

    km_orig = KMeans(n_clusters=K, random_state=42, n_init=20).fit(scaler_orig.transform(X_orig))
    km_cond = KMeans(n_clusters=K, random_state=42, n_init=20).fit(scaler_cond.transform(X_cond))

    grp["cluster_orig"] = km_orig.labels_
    grp["cluster_cond"] = km_cond.labels_

    # Summarise cluster mean fragility_z under each scheme
    orig_summary = (
        grp.groupby("cluster_orig")["fragility_z"]
        .agg(mean="mean", count="count")
        .sort_values("mean", ascending=False)
        .reset_index()
    )
    cond_summary = (
        grp.groupby("cluster_cond")["fragility_z_conditional"]
        .agg(mean="mean", count="count")
        .sort_values("mean", ascending=False)
        .reset_index()
    )

    print(f"\n{ba} — original clusters (by fragility_z):")
    for _, r in orig_summary.iterrows():
        print(f"  Cluster {int(r['cluster_orig'])}: mean fz = {r['mean']:.3f}  ({int(r['count'])} days)")

    print(f"\n{ba} — conditional clusters (by fragility_z_conditional):")
    for _, r in cond_summary.iterrows():
        print(f"  Cluster {int(r['cluster_cond'])}: mean fz_cond = {r['mean']:.3f}  ({int(r['count'])} days)")

    # Check how many days switch cluster tiers (extreme <-> moderate <-> stable)
    # Define tiers by rank of mean fragility within each scheme
    orig_tier = orig_summary.set_index("cluster_orig")["mean"].rank(ascending=False).astype(int)
    cond_tier = cond_summary.set_index("cluster_cond")["mean"].rank(ascending=False).astype(int)
    grp["tier_orig"] = grp["cluster_orig"].map(orig_tier)
    grp["tier_cond"] = grp["cluster_cond"].map(cond_tier)

    switched = (grp["tier_orig"] != grp["tier_cond"]).sum()
    print(f"\n  Days that switched fragility tier: {switched} / {len(grp)} ({switched/len(grp)*100:.1f}%)")


print("\n" + "=" * 65)
print("Done. No files were modified.")
print("=" * 65)
