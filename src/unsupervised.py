# src/unsupervised.py

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from pathlib import Path
import matplotlib.pyplot as plt




from src.config import DAILY_PARQUET_PATH, FEATURE_COLS, META_COLS


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

    print("\n--- DATA TYPES ---")
    print(df[FEATURE_COLS + META_COLS].dtypes)

    assert (
        df[META_COLS].drop_duplicates().shape[0] == len(df)
    ), "Duplicate BA-days detected (balancing_authority, date) must be unique."

    safe_print_ok("\n✅ Step 0 checks passed. Data is ML-ready.")


def step1_build_matrices(df: pd.DataFrame):
    """
    Returns:
      X_raw: feature matrix (n_rows x n_features)
      meta: metadata dataframe aligned row-for-row with X_raw
    """
    X_raw = df[FEATURE_COLS].copy()
    meta = df[META_COLS].copy()

    print("\n--- STEP 1: MATRIX SHAPES ---")
    print("X_raw shape:", X_raw.shape)
    print("meta shape:", meta.shape)

    assert len(X_raw) == len(meta), "X_raw and meta row counts do not match."

    print("\n--- STEP 1: PREVIEW (X_raw head) ---")
    print(X_raw.head(3))

    print("\n--- STEP 1: PREVIEW (meta head) ---")
    print(meta.head(3))

    safe_print_ok("\n✅ Step 1 complete: X_raw + meta built.")
    return X_raw, meta

def step2_standardize_within_ba(X_raw: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize features (z-score) *within* each balancing authority.

    Returns:
      X_scaled: same shape as X_raw, standardized per-BA
    """
    ba_col = "balancing_authority"
    assert ba_col in meta.columns, f"meta must include '{ba_col}'"

    X_scaled = X_raw.copy()

    for ba, idx in meta.groupby(ba_col).groups.items():
        scaler = StandardScaler()
        X_scaled.loc[idx, :] = scaler.fit_transform(X_raw.loc[idx, :].values)

    print("\n--- STEP 2: STANDARDIZATION CHECKS ---")
    # Means/stds should be ~0/~1 within each BA
    for ba, idx in meta.groupby(ba_col).groups.items():
        means = X_scaled.loc[idx, :].mean().round(3)
        stds = X_scaled.loc[idx, :].std(ddof=0).round(3)  # population std
        print(f"\nBA: {ba}")
        print("Mean (first 5):", means.head(5).to_dict())
        print("Std  (first 5):", stds.head(5).to_dict())

    safe_print_ok("\n✅ Step 2 complete: features standardized within BA.")
    return X_scaled

def step3_pca(X_scaled: pd.DataFrame, n_components: int = 3):
    """
    Fit PCA on standardized features.

    Returns:
      X_pca_df: DataFrame with PC1..PCn columns (aligned to rows)
      pca: fitted PCA object (for explained variance, loadings)
    """
    assert n_components >= 2, "Use at least 2 components for visualization."

    pca = PCA(n_components=n_components, random_state=42)
    X_pca = pca.fit_transform(X_scaled.values)

    pc_cols = [f"PC{i+1}" for i in range(n_components)]
    X_pca_df = pd.DataFrame(X_pca, columns=pc_cols, index=X_scaled.index)

    print("\n--- STEP 3: PCA ---")
    evr = pca.explained_variance_ratio_
    for i, v in enumerate(evr, start=1):
        print(f"Explained variance PC{i}: {v:.4f}")
    print(f"Total explained variance (PC1..PC{n_components}): {evr.sum():.4f}")

    safe_print_ok("\n✅ Step 3 complete: PCA fitted and transformed.")
    return X_pca_df, pca

def step4a_kmeans(X_pca_df: pd.DataFrame, k: int = 4):
    """
    Cluster PCA-reduced data using K-Means.

    Returns:
      clusters: array of cluster labels
      kmeans: fitted KMeans object
    """
    assert k >= 2, "k must be at least 2"

    kmeans = KMeans(
        n_clusters=k,
        random_state=42,
        n_init=20,
    )

    clusters = kmeans.fit_predict(X_pca_df.values)

    print(f"\n--- STEP 4: K-MEANS (k={k}) ---")
    print(pd.Series(clusters).value_counts().sort_index())

    return clusters, kmeans

def step4a_interpret_clusters(
    df: pd.DataFrame,
    clusters,
    feature_cols,
):
    """
    Summarize feature behavior by cluster.
    Returns:
      feature_means: mean of features by cluster
      fragility_tails: tail-risk summary of fragility_z by cluster
    """
    df_tmp = df.copy()
    df_tmp["cluster"] = clusters

    print("\n--- STEP 4A: CLUSTER COUNTS ---")
    print(df_tmp["cluster"].value_counts().sort_index())

    print("\n--- STEP 4A: CLUSTER FEATURE MEANS ---")
    feature_means = (
        df_tmp
        .groupby("cluster")[feature_cols]
        .mean()
        .round(3)
    )
    print(feature_means)

    # Tail risk table for fragility (this is the “extra table”)
    fragility_tails = (
        df_tmp
        .groupby("cluster")["fragility_z"]
        .agg(
            mean="mean",
            p90=lambda x: x.quantile(0.90),
            p95=lambda x: x.quantile(0.95),
            max="max",
            count="count",
        )
        .round(3)
    )

    print("\n--- STEP 4A: FRAGILITY TAILS BY CLUSTER ---")
    print(fragility_tails)

    return feature_means, fragility_tails

def _savefig(fig_dir: Path, filename: str):
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / filename
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Wrote figure: {path}")


def step4b_make_plots(df_plot: pd.DataFrame, fig_dir: str, k: int):
    fig_dir = Path(fig_dir)
    
    print("\n--- STEP 4B: GENERATING PLOTS ---")

    # ---- Plot 1: PCA colored by cluster (categorical legend) ----
    plt.figure(figsize=(8, 6))

    clusters_sorted = sorted(df_plot["cluster"].unique())
    cmap = plt.get_cmap("tab10")

    for i, cluster_id in enumerate(clusters_sorted):
        sub = df_plot[df_plot["cluster"] == cluster_id]
        plt.scatter(
            sub["PC1"],
            sub["PC2"],
            color=cmap(i),
            label=f"Cluster {cluster_id}",
            alpha=0.7,
            edgecolors="none",
        )

    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title(f"PCA (PC1 vs PC2) colored by K-Means cluster (k={k})")
    plt.legend(title="Cluster", loc="best")
    plt.tight_layout()
    _savefig(fig_dir, f"pca_pc1_pc2_by_cluster_k{k}.png")



    # ---- Plot 2: PCA colored by fragility ----
    print("Creating plot 2/5: PCA colored by fragility...")
    plt.figure(figsize=(8, 6))
    sc = plt.scatter(
        df_plot["PC1"],
        df_plot["PC2"],
        c=df_plot["fragility_z"],
        alpha=0.7,
    )
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title("PCA (PC1 vs PC2) colored by fragility_z")
    plt.colorbar(sc, label="fragility_z")
    _savefig(fig_dir, "pca_pc1_pc2_by_fragility.png")

    # ---- Plot 3: PCA colored by BA ----
    print("Creating plot 3/5: PCA colored by balancing authority...")
    plt.figure(figsize=(8, 6))
    for ba, sub in df_plot.groupby("balancing_authority"):
        plt.scatter(sub["PC1"], sub["PC2"], label=ba, alpha=0.6)
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title("PCA (PC1 vs PC2) colored by balancing_authority")
    plt.legend()
    _savefig(fig_dir, "pca_pc1_pc2_by_ba.png")

    # ---- Plot 4: Cluster counts by BA (bar chart) ----
    print("Creating plot 4/5: Cluster counts by balancing authority...")
    counts = (
        df_plot
        .groupby(["cluster", "balancing_authority"])
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )

    ax = counts.plot(kind="bar", figsize=(9, 6))
    ax.set_xlabel("cluster")
    ax.set_ylabel("days (count)")
    ax.set_title("Cluster counts by balancing authority")
    plt.tight_layout()
    _savefig(fig_dir, "cluster_counts_by_ba.png")

    # ---- Plot 5: Extreme cluster annotated (with legend) ----
    plt.figure(figsize=(8, 6))

    clusters_sorted = sorted(df_plot["cluster"].unique())
    cmap = plt.get_cmap("tab10")

    # Background: all clusters (faded)
    for i, cluster_id in enumerate(clusters_sorted):
        sub = df_plot[df_plot["cluster"] == cluster_id]
        plt.scatter(
            sub["PC1"],
            sub["PC2"],
            color=cmap(i),
            alpha=0.25,
            label=f"Cluster {cluster_id}",
            edgecolors="none",
        )

    # Identify extreme cluster (highest max fragility)
    extreme_cluster = (
        df_plot.groupby("cluster")["fragility_z"]
        .max()
        .idxmax()
    )

    extreme_points = df_plot[df_plot["cluster"] == extreme_cluster].copy()

    # Foreground: extreme cluster highlighted
    plt.scatter(
        extreme_points["PC1"],
        extreme_points["PC2"],
        color=cmap(clusters_sorted.index(extreme_cluster)),
        alpha=0.95,
        edgecolors="black",
        linewidths=0.5,
        s=70,
        label=f"Extreme cluster ({extreme_cluster})",
    )

    # Annotate up to 10 most extreme days
    extreme_points = extreme_points.sort_values("fragility_z", ascending=False).head(10)
    for _, r in extreme_points.iterrows():
        plt.annotate(
            str(r["date"])[:10],  # YYYY-MM-DD
            (r["PC1"], r["PC2"]),
            fontsize=8,
            xytext=(4, 4),
            textcoords="offset points",
        )

    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title(f"Extreme operating regime highlighted (cluster={extreme_cluster})")
    plt.legend(title="Cluster", loc="best")
    plt.tight_layout()
    _savefig(fig_dir, "pca_pc1_pc2_extremes_annotated.png")

    
    safe_print_ok("\n✅ Step 4b complete: All plots generated.")



def main():
    df = load_daily_df(DAILY_PARQUET_PATH)

    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])

    # step 0: sanity checks on full dataset
    step0_sanity_checks(df)

    # step 1: build matrices from full dataset
    X_raw, meta = step1_build_matrices(df)

    output_dir = Path("data/processed/unsupervised")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Run steps 2–4 independently per BA ──────────────────────────────────
    ba_results = []

    for ba in sorted(df["balancing_authority"].unique()):
        print(f"\n{'='*55}")
        print(f"  Processing BA: {ba}")
        print(f"{'='*55}")

        # Subset to this BA only (preserve original index for alignment)
        ba_idx = meta[meta["balancing_authority"] == ba].index
        X_raw_ba = X_raw.loc[ba_idx]
        meta_ba = meta.loc[ba_idx]
        df_ba = df.loc[ba_idx]

        # step 2: standardize (single BA — scaler fits on this BA alone)
        X_scaled_ba = step2_standardize_within_ba(X_raw_ba, meta_ba)

        # step 3: PCA
        X_pca_ba, _pca = step3_pca(X_scaled_ba, n_components=3)

        # step 4a: K-Means + interpretation
        clusters_ba, _kmeans = step4a_kmeans(X_pca_ba, k=4)

        feature_means_ba, fragility_tails_ba = step4a_interpret_clusters(
            df=df_ba,
            clusters=clusters_ba,
            feature_cols=FEATURE_COLS,
        )

        # Save per-BA summaries
        ba_dir = output_dir / ba.lower()
        ba_dir.mkdir(parents=True, exist_ok=True)

        feature_means_ba.to_csv(ba_dir / "cluster_feature_means.csv", index=True)
        fragility_tails_ba.to_csv(ba_dir / "cluster_fragility_tails.csv", index=True)
        print(f"Wrote per-BA summaries: {ba_dir}")

        # Build BA output dataframe
        df_out_ba = pd.concat(
            [df_ba.reset_index(drop=True),
             X_pca_ba.reset_index(drop=True)],
            axis=1
        )
        df_out_ba["cluster"] = clusters_ba

        # step 4b: plots (saved per BA)
        fig_dir = f"reports/figures/unsupervised/{ba.lower()}"
        step4b_make_plots(df_plot=df_out_ba, fig_dir=fig_dir, k=4)

        ba_results.append(df_out_ba)

    # ── Recombine and save combined output ───────────────────────────────────
    df_out = pd.concat(ba_results, ignore_index=True)

    print("\n--- CLUSTER PREVIEW (combined) ---")
    print(df_out[["cluster", "balancing_authority", "date"]].head())

    df_out.to_parquet(output_dir / "daily_with_clusters.parquet", index=False)
    df_out.to_csv(output_dir / "daily_with_clusters.csv", index=False)
    df_out.to_json(output_dir / "daily_with_clusters.json",
                   orient="records", date_format="iso", indent=2)

    print(f"\nWrote combined clustered data: {output_dir}")





if __name__ == "__main__":
    main()
