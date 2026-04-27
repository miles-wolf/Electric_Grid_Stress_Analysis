# Makefile (run commands from project root)
# Usage:
#   make ingest
#   make qc
#   make all
#   make pipeline

.PHONY: ingest features fragility_daily unsupervised storytelling validate qc pipeline

ingest:
	python src/ingest_eia930.py

features:
	python -m src.features_eia930 \
	  --in data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet \
	  --out data/processed/features/eia930_daily_features_2025_pjm_ciso.parquet

# Daily fragility metrics + plots
fragility_daily:
	python src/fragility_daily.py

# Per-BA clustering and unsupervised ML
unsupervised:
	python -m src.unsupervised

# Storytelling figures (Module 5)
storytelling:
	python src/storytelling/plot_regimes_feature_space.py
	python src/storytelling/plot_fragility_by_cluster.py
	python src/storytelling/plot_frequency_vs_fragility.py
	python src/storytelling/plot_temporal_trajectories.py

# Statistical validation analysis
validate:
	python -m src.analysis_validation

# Data quality check
qc:
	python src/qc_eia930.py

# Full end-to-end pipeline
pipeline: ingest fragility_daily unsupervised storytelling validate qc


