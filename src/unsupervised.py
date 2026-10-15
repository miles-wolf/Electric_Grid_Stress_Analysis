# src/unsupervised.py

import pandas as pd
from sklearn.cluster import KMeans
from pathlib import Path
import matplotlib.pyplot as plt

from src.config import DAILY_PARQUET_PATH, FEATURE_COLS, META_COLS, CHARACTERIZATION_COLS


def safe_print_ok(msg: str) -> None:
    """Avoid Windows console unicode issues."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "ignore").decode("ascii"))


def load_daily_df(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


def step0_sanity_checks(df: pd.DataFrame) -> None:
    print("\n--- BASIC SHAPE ---")
    print("Rows:", len(df))
    print("Unique BA-days:", df[META_COLS].drop_duplicates().shape[0])

    print("\n--- BALANCING AUTHORITIES ---")
    print(df["balancing_authority"].value_counts())

    print("\n--- DATE RANGE ---")
    print("Min date:", df["date"].min())
    print("Max date:", df["date"].max())

    print("\n--- COLUMN INVENTORY ---")
    print(sorted(df.columns.tolist()))

    print("\n--- FEATURE MISSINGNESS ---")
    print(df[FEATURE_COLS].isna().mean().sort_values())

    print("\n--- FEATURE RANGES ---")
    print(df[FEATURE_COLS].describe().T[["min", "mean", "max"]])

    assert (
        df[META_COLS].drop_duplicates().shape[0] == len(df)
    ), "Duplicate BA-days detected (balancing_authority, date) must be unique."

    safe_print_ok("\n[OK] Step 0 checks passed. Data is ML-ready.")


def step1_build_matrix(df: pd.DataFrame):
    """
    Returns:
      X: feature matrix using FEATURE_COLS directly. Features are already
         z-scored within-BA by stress_daily.py, so no further scaling or
         dimensionality reduction is required.
      meta: metadata dataframe aligned row-for-row with X.
    """
    X = df[FEATURE_COLS].copy()
    meta = df[META_COLS].copy()

    print("\n--- STEP 1: MATRIX SHAPES ---")
    print("X shape:", X.shape)
    print("Features:", FEATURE_COLS)
    print("meta shape:", meta.shape)

    assert len(X) == len(meta), "X and meta row counts do not match."
    safe_print_ok("[OK] Step 1 complete: feature matrix built.")
    return X, meta


def step2_kmeans(X: pd.DataFrame, k: int = 4):
    """
    Cluster directly on the (already z-scored) feature matrix.

    Returns:
      clusters: array of cluster labels
      kmeans: fitted KMeans object
    """
    assert k >= 2, "k must be at least 2"

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=20)
    clusters = kmeans.fit_predict(X.values)

    print(f"\n--- STEP 2: K-MEANS (k={k}) ---")
    print(pd.Series(clusters).value_counts().sort_index())

    return clusters, kmeans


def step3_interpret_clusters(
    df: pd.DataFrame,
    clusters,
    feature_cols,
    characterization_cols=None,
):
    """
    Summarize cluster profiles: mean feature values, season composition,
    cluster size, and stress_z tail risk per cluster.
    """
    df_tmp = df.copy()
    df_tmp["cluster"] = clusters

    print("\n--- STEP 3: CLUSTER COUNTS ---")
    print(df_tmp["cluster"].value_counts().sort_index())

    profile_cols = feature_cols + (characterization_cols or [])

    feature_means = (
        df_tmp.groupby("cluster")[profile_cols]
        .mean()
        .round(3)
    )
    feature_means["n_days"] = df_tmp.groupby("cluster").size()

    if "season" in df_tmp.columns:
        season_counts = (
            df_tmp.groupby(["cluster", "season"])
            .size()
            .unstack(fill_value=0)
        )
        season_share = season_counts.div(season_counts.sum(axis=1), axis=0).round(3)
        season_share.columns = [f"pct_{s.lower()}" for s in season_share.columns]
        feature_means = feature_means.join(season_share)

    print("\n--- STEP 3: CLUSTER FEATURE MEANS + SEASON COMPOSITION ---")
    print(feature_means)

    stress_tails = (
        df_tmp.groupby("cluster")["stress_z"]
        .agg(
            mean="mean",
            p90=lambda x: x.quantile(0.90),
            p95=lambda x: x.quantile(0.95),
            max="max",
            count="count",
        )
        .round(3)
    )

    print("\n--- STEP 3: STRESS TAILS BY CLUSTER ---")
    print(stress_tails)

    return feature_means, stress_tails


def _savefig(fig_dir: Path, filename: str):
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / filename
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote figure: {path}")


def step4_make_plots(df_plot: pd.DataFrame, fig_dir: str, k: int):
    """All scatter plots use z_daily_peak_mw (x) vs z_daily_max_ramp_mw (y)."""
    fig_dir = Path(fig_dir)
    print("\n--- STEP 4: GENERATING PLOTS ---")

    x_col = "z_daily_peak_mw"
    y_col = "z_daily_max_ramp_mw"
    cmap = plt.get_cmap("tab10")
    clusters_sorted = sorted(df_plot["cluster"].unique())
    season_cmap = {"Summer": "tab:red", "Winter": "tab:blue", "Shoulder": "tab:olive"}

    # Plot 1: feature space colored by cluster
    plt.figure(figsize=(8, 6))
    for i, cluster_id in enumerate(clusters_sorted):
        sub = df_plot[df_plot["cluster"] == cluster_id]
        plt.scatter(sub[x_col], sub[y_col], color=cmap(i),
                    label=f"Cluster {cluster_id}", alpha=0.7, edgecolors="none")
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(f"Feature space colored by K-Means cluster (k={k})")
    plt.legend(title="Cluster", loc="best")
    plt.axhline(0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.axvline(0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    _savefig(fig_dir, f"feature_space_by_cluster_k{k}.png")

    # Plot 2: feature space colored by stress_z
    plt.figure(figsize=(8, 6))
    sc = plt.scatter(df_plot[x_col], df_plot[y_col], c=df_plot["stress_z"], alpha=0.7)
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title("Feature space colored by stress_z")
    plt.colorbar(sc, label="stress_z")
    plt.axhline(0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.axvline(0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    _savefig(fig_dir, "feature_space_by_stress.png")

    # Plot 3: feature space colored by season
    if "season" in df_plot.columns:
        plt.figure(figsize=(8, 6))
        for season in sorted(df_plot["season"].dropna().unique()):
            sub = df_plot[df_plot["season"] == season]
            plt.scatter(sub[x_col], sub[y_col],
                        color=season_cmap.get(season, "gray"),
                        label=season, alpha=0.6, edgecolors="none")
        plt.xlabel(x_col)
        plt.ylabel(y_col)
        plt.title("Feature space colored by season")
        plt.legend(title="Season", loc="best")
        plt.tight_layout()
        _savefig(fig_dir, "feature_space_by_season.png")

    # Plot 4: cluster counts by season
    if "season" in df_plot.columns:
        counts = (
            df_plot.groupby(["cluster", "season"])
            .size()
            .unstack(fill_value=0)
            .sort_index()
        )
        ax = counts.plot(
            kind="bar",
            figsize=(9, 6),
            color=[season_cmap.get(s, "gray") for s in counts.columns],
        )
        ax.set_xlabel("cluster")
        ax.set_ylabel("days (count)")
        ax.set_title("Cluster counts by season")
        plt.tight_layout()
        _savefig(fig_dir, "cluster_counts_by_season.png")

    # Plot 5: extreme cluster annotated
    plt.figure(figsize=(8, 6))
    for i, cluster_id in enumerate(clusters_sorted):
        sub = df_plot[df_plot["cluster"] == cluster_id]
        plt.scatter(sub[x_col], sub[y_col], color=cmap(i), alpha=0.25,
                    label=f"Cluster {cluster_id}", edgecolors="none")
    extreme_cluster = df_plot.groupby("cluster")["stress_z"].max().idxmax()
    extreme_points = df_plot[df_plot["cluster"] == extreme_cluster].copy()
    plt.scatter(
        extreme_points[x_col], extreme_points[y_col],
        color=cmap(clusters_sorted.index(extreme_cluster)),
        alpha=0.95, edgecolors="black", linewidths=0.5, s=70,
        label=f"Extreme cluster ({extreme_cluster})",
    )
    extreme_points = extreme_points.sort_values("stress_z", ascending=False).head(10)
    for _, r in extreme_points.iterrows():
        plt.annotate(
            str(r["date"])[:10], (r[x_col], r[y_col]),
            fontsize=8, xytext=(4, 4), textcoords="offset points",
        )
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(f"Extreme operating regime highlighted (cluster={extreme_cluster})")
    plt.legend(title="Cluster", loc="best")
    plt.tight_layout()
    _savefig(fig_dir, "feature_space_extremes_annotated.png")

    safe_print_ok("[OK] Step 4 complete: all plots generated.")


def main():
    df = load_daily_df(DAILY_PARQUET_PATH)
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])

    step0_sanity_checks(df)
    _, meta = step1_build_matrix(df)

    output_dir = Path("data/processed/unsupervised")
    output_dir.mkdir(parents=True, exist_ok=True)

    ba_results = []

    for ba in sorted(df["balancing_authority"].unique()):
        print(f"\n{'='*55}")
        print(f"  Processing BA: {ba}")
        print(f"{'='*55}")

        ba_idx = meta[meta["balancing_authority"] == ba].index
        df_ba = df.loc[ba_idx]
        X_ba = df_ba[FEATURE_COLS]

        clusters_ba, _ = step2_kmeans(X_ba, k=4)

        feature_means_ba, stress_tails_ba = step3_interpret_clusters(
            df=df_ba,
            clusters=clusters_ba,
            feature_cols=FEATURE_COLS,
            characterization_cols=CHARACTERIZATION_COLS,
        )

        ba_dir = output_dir / ba.lower()
        ba_dir.mkdir(parents=True, exist_ok=True)
        feature_means_ba.to_csv(ba_dir / "cluster_feature_means.csv", index=True)
        stress_tails_ba.to_csv(ba_dir / "cluster_stress_tails.csv", index=True)
        print(f"Wrote per-BA summaries: {ba_dir}")

        df_out_ba = df_ba.reset_index(drop=True).copy()
        df_out_ba["cluster"] = clusters_ba

        fig_dir = f"reports/figures/unsupervised/{ba.lower()}"
        step4_make_plots(df_plot=df_out_ba, fig_dir=fig_dir, k=4)

        ba_results.append(df_out_ba)

    df_out = pd.concat(ba_results, ignore_index=True)

    print("\n--- CLUSTER PREVIEW (combined) ---")
    print(df_out[["cluster", "balancing_authority", "date"]].head())

    df_out.to_parquet(output_dir / "daily_with_clusters.parquet", index=False)
    df_out.to_csv(output_dir / "daily_with_clusters.csv", index=False)
    df_out.to_json(
        output_dir / "daily_with_clusters.json",
        orient="records", date_format="iso", indent=2,
    )

    print(f"\nWrote combined clustered data: {output_dir}")


if __name__ == "__main__":
    main()
