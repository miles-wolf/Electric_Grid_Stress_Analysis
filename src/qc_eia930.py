from pathlib import Path
import pandas as pd

FILE_PARQUET = Path("data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet")
FILE_CSV = Path("data/processed/eia930/eia930_balance_2025_pjm_ciso.csv")

def main():
    if FILE_PARQUET.exists():
        df = pd.read_parquet(FILE_PARQUET)
        src = FILE_PARQUET
    elif FILE_CSV.exists():
        df = pd.read_csv(FILE_CSV)
        src = FILE_CSV
    else:
        raise FileNotFoundError("No processed file found. Run ingestion first.")
    
    expected = 365 * 24 * 2  # 2025 full year * hourly * 2 BAs
    if len(df) != expected:
        print(f"WARNING: expected {expected} rows, got {len(df)}")


    print("QC SOURCE:", src)
    print("rows:", len(df))
    if "balancing_authority" in df.columns:
        print("BAs:", sorted(df["balancing_authority"].dropna().unique().tolist()))
    for col in ["timestamp_utc", "utc_time_at_end_of_hour", "demand_(mw)", "demand_(mw)_(adjusted)"]:
        if col in df.columns:
            print(f"missing {col}:", df[col].isna().mean())

    # quick timestamp range
    if "timestamp_utc" in df.columns:
        print("min timestamp_utc:", df["timestamp_utc"].min())
        print("max timestamp_utc:", df["timestamp_utc"].max())

if __name__ == "__main__":
    main()
