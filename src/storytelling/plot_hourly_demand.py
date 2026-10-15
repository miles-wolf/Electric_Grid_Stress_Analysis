"""
Appendix A: Hourly Demand Profiles for Extreme Stress Days

Figures (reports/figures/storytelling/appendix_hourly/):
  A1_ciso_duck_curve.png      — CAISO Sept 3 2025: demand / solar / net load / ramp
  A2_pjm_summer_vs_winter.png — PJM June 24 (Summer) vs Jan 23 (Winter): demand / ramp

Tables (data/processed/appendix/):
  ciso_peak_hourly.csv
  pjm_summer_peak_hourly.csv
  pjm_winter_peak_hourly.csv
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

HOURLY_PATH = Path("data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet")
FIG_DIR     = Path("reports/figures/storytelling/appendix_hourly")
TABLE_DIR   = Path("data/processed/appendix")
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

# Event dates (local date strings matching EIA-930 data_date format MM/DD/YYYY)
CISO_PEAK_DATE   = "09/03/2025"   # Rank-1 CISO summer event  (stress_z = 6.60)
PJM_SUMMER_DATE  = "06/24/2025"   # Rank-1 PJM  summer event  (stress_z = 4.83)
PJM_WINTER_DATE  = "01/23/2025"   # Top PJM winter day        (stress_z = 2.34)

SOLAR_COLS_ADJ = [
    "net_generation_(mw)_from_solar_without_integrated_battery_storage_(adjusted)",
    "net_generation_(mw)_from_solar_witho_integrated_battery_storage_(adjusted)",
]

MW_FMT = mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_day(hourly: pd.DataFrame, ba: str, date_str: str) -> pd.DataFrame:
    day = (
        hourly[(hourly["balancing_authority"] == ba) & (hourly["data_date"] == date_str)]
        .sort_values("hour_number")
        .copy()
    )
    day["demand_mw"] = day["demand_(mw)_(adjusted)"]

    # Total solar; clamp to >= 0 (small negative values are battery artefacts)
    solar = pd.Series(np.zeros(len(day)), index=day.index)
    for col in SOLAR_COLS_ADJ:
        if col in day.columns:
            solar += day[col].fillna(0)
    day["solar_mw"]   = solar.clip(lower=0).values
    day["net_load_mw"] = day["demand_mw"] - day["solar_mw"]
    day["ramp_demand_mw"]  = day["demand_mw"].diff()
    day["ramp_netload_mw"] = day["net_load_mw"].diff()
    return day.reset_index(drop=True)


def fmt_hour(h: int) -> str:
    """Hour number (1–24) → 'HH:00' label."""
    display = h % 24   # hour 24 → 0
    return f"{display:02d}:00"


# ---------------------------------------------------------------------------
# Figure A1: CAISO duck curve on the peak stress day
# ---------------------------------------------------------------------------

def plot_ciso_duck_curve(hourly: pd.DataFrame):
    day   = load_day(hourly, "CISO", CISO_PEAK_DATE)
    hours = day["hour_number"].values
    xlabs = [fmt_hour(h) for h in hours]

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(13, 9), gridspec_kw={"height_ratios": [3, 2]}
    )

    # ---- Top panel: demand / solar / net load ----
    ax_top.fill_between(hours, 0, day["solar_mw"],
                        color="#FFD166", alpha=0.65, label="Solar generation (MW)")
    ax_top.plot(hours, day["demand_mw"],
                color="#2C7BB6", lw=2.2, label="Gross demand (MW)")
    ax_top.plot(hours, day["net_load_mw"],
                color="#D7191C", lw=2.5, label="Net load = demand − solar (MW)")

    # Duck trough annotation
    trough_h   = int(day.loc[day["net_load_mw"].idxmin(), "hour_number"])
    trough_val = day.loc[day["net_load_mw"].idxmin(), "net_load_mw"]
    ax_top.annotate(
        f"Duck trough\n{trough_val/1000:.1f}k MW (hr {trough_h:02d}:00)",
        xy=(trough_h, trough_val),
        xytext=(trough_h - 3.5, trough_val + 4500),
        fontsize=9, color="#D7191C",
        arrowprops=dict(arrowstyle="->", color="#D7191C", lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#D7191C", alpha=0.85),
    )

    # Evening ramp annotation
    ramp_h   = int(day.loc[day["ramp_netload_mw"].idxmax(), "hour_number"])
    ramp_val = day.loc[day["ramp_netload_mw"].idxmax(), "ramp_netload_mw"]
    ax_top.annotate(
        f"Max evening ramp\n+{ramp_val/1000:.1f}k MW in 1 hr (hr {ramp_h:02d}:00)",
        xy=(ramp_h, day.loc[day["hour_number"] == ramp_h, "net_load_mw"].values[0]),
        xytext=(ramp_h + 0.8, day.loc[day["hour_number"] == ramp_h, "net_load_mw"].values[0] - 7000),
        fontsize=9, color="#8B0000",
        arrowprops=dict(arrowstyle="->", color="#8B0000", lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#8B0000", alpha=0.85),
    )

    ax_top.axvspan(17, 21, color="#D7191C", alpha=0.07, label="Evening ramp window")
    ax_top.set_ylabel("MW", fontsize=13)
    ax_top.yaxis.set_major_formatter(MW_FMT)
    ax_top.set_xticks(hours[::2])
    ax_top.set_xticklabels(xlabs[::2], fontsize=9, rotation=30)
    ax_top.set_xlim(1, 24)
    ax_top.legend(fontsize=10, loc="upper left", framealpha=0.9)
    ax_top.grid(alpha=0.3)
    ax_top.set_title(
        "CAISO — Sept 3, 2025 (Rank-1 Summer Stress Event, stress z = 6.60)",
        fontsize=13, fontweight="bold"
    )

    # ---- Bottom panel: net load ramp bars ----
    colors = ["#D7191C" if r > 0 else "#4575B4" for r in day["ramp_netload_mw"].fillna(0)]
    ax_bot.bar(hours, day["ramp_netload_mw"].fillna(0), color=colors, width=0.7, zorder=3)
    ax_bot.axhline(0, color="black", lw=0.8, alpha=0.6)
    ax_bot.axvspan(17, 21, color="#D7191C", alpha=0.07)

    max_ramp_h = int(day.loc[day["ramp_netload_mw"].idxmax(), "hour_number"])
    max_ramp_v = day["ramp_netload_mw"].max()
    ax_bot.annotate(
        f"+{max_ramp_v/1000:.1f}k MW/hr",
        xy=(max_ramp_h, max_ramp_v),
        xytext=(max_ramp_h + 1, max_ramp_v - 1500),
        fontsize=9, color="#8B0000", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#8B0000", lw=1.0),
    )

    ax_bot.set_xlabel("Hour (local time)", fontsize=13)
    ax_bot.set_ylabel("Ramp (MW/hr)", fontsize=13)
    ax_bot.yaxis.set_major_formatter(MW_FMT)
    ax_bot.set_xticks(hours[::2])
    ax_bot.set_xticklabels(xlabs[::2], fontsize=9, rotation=30)
    ax_bot.set_xlim(1, 24)
    ax_bot.grid(alpha=0.3, zorder=0)
    ax_bot.set_title(
        "Net Load Hourly Ramp Rate  (red = demand rising faster than solar; blue = net load declining)",
        fontsize=11
    )

    fig.suptitle(
        "Solar Duck Curve — CAISO Peak Stress Day\n"
        "Solar displaces midday demand, then drops sharply into evening peak, creating the catastrophic net-load ramp",
        fontsize=14, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    out = FIG_DIR / "A1_ciso_duck_curve.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {out}")


# ---------------------------------------------------------------------------
# Figure A2: PJM Summer vs Winter hourly demand + ramp
# ---------------------------------------------------------------------------

def plot_pjm_summer_vs_winter(hourly: pd.DataFrame):
    summer = load_day(hourly, "PJM", PJM_SUMMER_DATE)
    winter = load_day(hourly, "PJM", PJM_WINTER_DATE)

    fig, axes = plt.subplots(2, 2, figsize=(16, 9), sharey="row")
    (ax_sd, ax_wd), (ax_sr, ax_wr) = axes

    hours  = summer["hour_number"].values
    xlabs  = [fmt_hour(h) for h in hours]
    xticks = hours[::3]
    xlabs3 = [fmt_hour(h) for h in xticks]

    def demand_panel(ax, day, title, color):
        ax.plot(day["hour_number"], day["demand_mw"], color=color, lw=2.5)
        ax.fill_between(day["hour_number"], day["demand_mw"].min() * 0.97,
                        day["demand_mw"], color=color, alpha=0.12)
        peak_h   = int(day.loc[day["demand_mw"].idxmax(), "hour_number"])
        peak_val = day["demand_mw"].max()
        ax.axvline(peak_h, color=color, lw=1.2, ls="--", alpha=0.7)
        ax.text(peak_h + 0.3, peak_val * 0.998,
                f"Peak: {peak_val/1000:.1f}k MW\n(hr {peak_h:02d}:00)",
                fontsize=9, color=color, va="top",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=color, alpha=0.85))
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_ylabel("Demand (MW)", fontsize=12)
        ax.yaxis.set_major_formatter(MW_FMT)
        ax.set_xticks(xticks); ax.set_xticklabels(xlabs3, fontsize=9, rotation=30)
        ax.set_xlim(1, 24); ax.grid(alpha=0.3)

    def ramp_panel(ax, day, color):
        ramp   = day["ramp_demand_mw"].fillna(0)
        colors = [color if r > 0 else "#999999" for r in ramp]
        ax.bar(day["hour_number"], ramp, color=colors, width=0.7, zorder=3)
        ax.axhline(0, color="black", lw=0.8, alpha=0.6)
        max_h = int(day.loc[day["ramp_demand_mw"].idxmax(), "hour_number"])
        max_v = day["ramp_demand_mw"].max()
        ax.annotate(
            f"+{max_v/1000:.1f}k MW/hr\n(hr {max_h:02d}:00)",
            xy=(max_h, max_v),
            xytext=(max_h + 1.2, max_v * 0.85),
            fontsize=9, color=color, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=color, lw=1.0),
        )
        ax.set_xlabel("Hour (local time)", fontsize=12)
        ax.set_ylabel("Ramp (MW/hr)", fontsize=12)
        ax.yaxis.set_major_formatter(MW_FMT)
        ax.set_xticks(xticks); ax.set_xticklabels(xlabs3, fontsize=9, rotation=30)
        ax.set_xlim(1, 24); ax.grid(alpha=0.3, zorder=0)

    demand_panel(ax_sd, summer,
                 "PJM Summer — June 24, 2025\n(Rank-1 event, stress z = 4.83)",
                 "#D7191C")
    demand_panel(ax_wd, winter,
                 "PJM Winter — Jan 23, 2025\n(Top winter stress day, stress z = 2.34)",
                 "#2C7BB6")
    ramp_panel(ax_sr, summer, "#D7191C")
    ramp_panel(ax_wr, winter, "#2C7BB6")

    # Annotate the structural difference
    ax_sd.text(0.03, 0.05,
               "Gradual mid-morning ramp\n(AC load builds with heat)",
               transform=ax_sd.transAxes, fontsize=9, color="#555555", style="italic",
               bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#aaaaaa", alpha=0.8))
    ax_wd.text(0.03, 0.05,
               "Sharp pre-dawn heating spike\n(thermostats at coldest hour)",
               transform=ax_wd.transAxes, fontsize=9, color="#555555", style="italic",
               bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#aaaaaa", alpha=0.8))

    fig.suptitle(
        "PJM Hourly Demand Profile: Summer vs Winter Extreme Stress Days\n"
        "Summer = sustained afternoon peak (heat dome);  Winter = sharp morning heating spike (polar vortex)",
        fontsize=14, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    out = FIG_DIR / "A2_pjm_summer_vs_winter.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote {out}")


# ---------------------------------------------------------------------------
# Summary tables
# ---------------------------------------------------------------------------

def save_tables(hourly: pd.DataFrame):
    # CAISO
    ciso = load_day(hourly, "CISO", CISO_PEAK_DATE)
    ciso_tbl = ciso[[
        "hour_number", "demand_mw", "solar_mw", "net_load_mw", "ramp_netload_mw"
    ]].copy()
    ciso_tbl.columns = ["hour", "demand_mw", "solar_mw", "net_load_mw", "ramp_net_load_mw"]
    ciso_tbl = ciso_tbl.round(0).astype({"hour": int})
    ciso_tbl.to_csv(TABLE_DIR / "ciso_peak_hourly.csv", index=False)
    print(f"Wrote {TABLE_DIR}/ciso_peak_hourly.csv")

    # PJM Summer
    pjm_s = load_day(hourly, "PJM", PJM_SUMMER_DATE)
    pjm_s_tbl = pjm_s[["hour_number", "demand_mw", "ramp_demand_mw"]].copy()
    pjm_s_tbl.columns = ["hour", "demand_mw", "ramp_mw"]
    pjm_s_tbl = pjm_s_tbl.round(0).astype({"hour": int})
    pjm_s_tbl.to_csv(TABLE_DIR / "pjm_summer_peak_hourly.csv", index=False)
    print(f"Wrote {TABLE_DIR}/pjm_summer_peak_hourly.csv")

    # PJM Winter
    pjm_w = load_day(hourly, "PJM", PJM_WINTER_DATE)
    pjm_w_tbl = pjm_w[["hour_number", "demand_mw", "ramp_demand_mw"]].copy()
    pjm_w_tbl.columns = ["hour", "demand_mw", "ramp_mw"]
    pjm_w_tbl = pjm_w_tbl.round(0).astype({"hour": int})
    pjm_w_tbl.to_csv(TABLE_DIR / "pjm_winter_peak_hourly.csv", index=False)
    print(f"Wrote {TABLE_DIR}/pjm_winter_peak_hourly.csv")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    hourly = pd.read_parquet(HOURLY_PATH)
    plot_ciso_duck_curve(hourly)
    plot_pjm_summer_vs_winter(hourly)
    save_tables(hourly)


if __name__ == "__main__":
    main()
