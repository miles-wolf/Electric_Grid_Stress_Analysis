# src/config.py

# -----------------------
# Data paths
# -----------------------
DAILY_PARQUET_PATH = "data/processed/fragility/daily_fragility_pjm_ciso_2025.parquet"

# -----------------------
# Column roles
# -----------------------
META_COLS = [
    "balancing_authority",
    "date",
]

FEATURE_COLS = [
    "daily_peak_mw",
    "daily_min_mw",
    "daily_range_mw",
    "daily_max_ramp_mw",
    "daily_ramp_std",
    "pct_hours_near_peak",
    "z_daily_peak_mw",
    "z_daily_max_ramp_mw",
    "z_pct_hours_near_peak",
    "fragility_z",
]
