# src/ingest_eia930.py

from pathlib import Path
import pandas as pd


RAW_DIR = Path("data/raw/eia930")
PROCESSED_DIR = Path("data/processed/eia930")
REGIONS_FILE = Path("data/raw/regions.txt")

FILES = [
    RAW_DIR / "EIA930_BALANCE_2025_Jan_Jun.csv",
    RAW_DIR / "EIA930_BALANCE_2025_Jul_Dec.csv",
]

OUTPUT_FILE = PROCESSED_DIR / "eia930_balance_2025_pjm_ciso.parquet"


def load_regions(path: Path) -> list[str]:
    return [r.strip() for r in path.read_text().splitlines() if r.strip()]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def main():
    regions = load_regions(REGIONS_FILE)
    print("Regions:", regions)

    dfs = []

    for file in FILES:
        print(f"Loading {file}")
        df = pd.read_csv(file, low_memory=False)
        df = normalize_columns(df)

        if "balancing_authority" not in df.columns:
            raise ValueError("Expected 'balancing_authority' column")

        df = df[df["balancing_authority"].isin(regions)].copy()
        dfs.append(df)

    out = pd.concat(dfs, ignore_index=True)
    print("Rows after filter:", len(out))
    print("Unique BAs:", sorted(out["balancing_authority"].unique()))

    # Timestamp handling
    if "utc_time_at_end_of_hour" in out.columns:
        out["timestamp_utc"] = pd.to_datetime(
            out["utc_time_at_end_of_hour"], errors="coerce"
        )
    elif "local_time_at_end_of_hour" in out.columns:
        out["timestamp_local"] = pd.to_datetime(
            out["local_time_at_end_of_hour"], errors="coerce"
        )

    # Basic QC
    if "timestamp_utc" in out.columns:
        print("Missing timestamp_utc:", out["timestamp_utc"].isna().mean())

    if "demand_(mw)" in out.columns:
        print("Missing demand_(mw):", out["demand_(mw)"].isna().mean())

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_FILE, index=False)

    size_mb = OUTPUT_FILE.stat().st_size / 1e6
    print(f"Wrote {OUTPUT_FILE} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
