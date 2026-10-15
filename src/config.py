# src/config.py

# -----------------------
# Data paths
# -----------------------
DAILY_PARQUET_PATH = "data/processed/stress/daily_stress_pjm_ciso_2025.parquet"

# -----------------------
# Column roles
# -----------------------
META_COLS = [
    "balancing_authority",
    "date",
]

FEATURE_COLS = [
    "z_daily_peak_mw",
    "z_daily_max_ramp_mw",
]

CHARACTERIZATION_COLS = [
    "stress_z",
    "daily_peak_mw",
    "daily_max_ramp_mw",
    "daily_energy_mwh",
]
