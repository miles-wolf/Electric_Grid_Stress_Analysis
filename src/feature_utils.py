import numpy as np
import pandas as pd


EPS = 1e-9

_SPIKE_WINDOW = 3
_SPIKE_MAX_CONSECUTIVE = 1
_SPIKE_DAILY_RANGE_FRAC = 0.25


def repair_demand_spikes(
    df: pd.DataFrame,
    ba_col: str,
    ts_col: str,
    demand_col: str,
) -> pd.DataFrame:
    """
    Detect and repair isolated single-hour demand spikes/dips caused by
    data reporting errors (e.g., a value dropped to an implausible level and
    immediately corrected in the next hour).

    Detection: a reading is flagged when it deviates from its 3-hour centered
    rolling median by more than _SPIKE_DAILY_RANGE_FRAC x that day's demand
    range. Using the day's own range as the scale reference means the threshold
    is self-calibrating across BAs of different sizes.

    Only runs of at most _SPIKE_MAX_CONSECUTIVE consecutive flagged hours are
    repaired. Longer runs are left untouched because they may reflect real
    operational events rather than data artifacts.

    Flagged values are replaced by linear interpolation.
    """
    df = df.copy().sort_values([ba_col, ts_col]).reset_index(drop=True)
    total_repaired = 0

    for ba, grp in df.groupby(ba_col, sort=True):
        idx = grp.index
        demand = grp[demand_col].astype(float).copy()
        dates = grp[ts_col].dt.date

        daily_range = demand.groupby(dates).transform(lambda x: x.max() - x.min())
        daily_range = daily_range.fillna(demand.std())

        rolling_med = demand.rolling(
            window=_SPIKE_WINDOW, center=True, min_periods=2
        ).median()

        spike_mask = (
            (demand - rolling_med).abs() > _SPIKE_DAILY_RANGE_FRAC * daily_range
        ).values.copy()

        i = 0
        while i < len(spike_mask):
            if spike_mask[i]:
                run_start = i
                while i < len(spike_mask) and spike_mask[i]:
                    i += 1
                if (i - run_start) > _SPIKE_MAX_CONSECUTIVE:
                    spike_mask[run_start:i] = False
            else:
                i += 1

        n = int(spike_mask.sum())
        if n > 0:
            repaired = demand.copy()
            repaired.iloc[np.where(spike_mask)[0]] = np.nan
            repaired = repaired.interpolate(method="linear", limit_direction="both")
            df.loc[idx, demand_col] = repaired.values

            for pos in np.where(spike_mask)[0]:
                print(
                    f"  [spike_repair] BA={ba}"
                    f"  ts={grp[ts_col].iloc[pos]}"
                    f"  original={demand.iloc[pos]:.0f} MW -> interpolated"
                )
            total_repaired += n

    if total_repaired == 0:
        print("  [spike_repair] No spikes detected.")
    else:
        print(f"  [spike_repair] Total hourly readings repaired: {total_repaired}")

    return df


def add_size_normalized_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds BA-size-normalized stress features.
    """
    df = df.copy()

    df["max_abs_ramp_pct_mean"] = df["max_abs_ramp_mw"] / (df["demand_mean_mw"] + EPS)
    df["ramp_p95_abs_pct_mean"] = df["ramp_p95_abs_mw"] / (df["demand_mean_mw"] + EPS)
    df["intra_day_range_pct_mean"] = df["intra_day_range_mw"] / (df["demand_mean_mw"] + EPS)
    df["demand_std_pct_mean"] = df["demand_std_mw"] / (df["demand_mean_mw"] + EPS)

    return df


def add_rolling_zscores(
    df: pd.DataFrame,
    group_col: str,
    time_col: str,
    cols: list[str],
    window: int = 7,
    min_periods: int = 4,
) -> pd.DataFrame:
    """
    Adds rolling z-score columns per group.
    """
    df = df.sort_values([group_col, time_col]).copy()

    def _z(s: pd.Series) -> pd.Series:
        mu = s.rolling(window, min_periods=min_periods).mean()
        sd = s.rolling(window, min_periods=min_periods).std()
        return (s - mu) / (sd + EPS)

    for c in cols:
        df[f"{c}_z{window}"] = (
            df.groupby(group_col)[c]
              .apply(_z)
              .reset_index(level=0, drop=True)
        )

    return df
