# Makefile (run commands from project root)
# Usage:
#   make ingest
#   make qc
#   make all
#   make pipeline

.PHONY: ingest features stress_daily unsupervised storytelling validate event_composite qc pipeline datacenters

ingest:
	python src/ingest_eia930.py

features:
	python -m src.features_eia930 \
	  --in data/processed/eia930/eia930_balance_2025_pjm_ciso.parquet \
	  --out data/processed/features/eia930_daily_features_2025_pjm_ciso.parquet

# Daily demand stress metrics + plots
stress_daily:
	python -m src.stress_daily

# Per-BA clustering and unsupervised ML
unsupervised:
	python -m src.unsupervised

# Storytelling figures (Module 5)
storytelling:
	python src/storytelling/plot_regimes_feature_space.py
	python src/storytelling/plot_stress_by_cluster.py
	python src/storytelling/plot_frequency_vs_stress.py
	python src/storytelling/plot_temporal_trajectories.py

# Statistical validation analysis
validate:
	python -m src.analysis_validation
	python -m src.validation_duration

# Event composite analysis (Module 7)
event_composite:
	python -m src.event_composite

# Data quality check
qc:
	python src/qc_eia930.py

# Full end-to-end pipeline
pipeline: ingest stress_daily unsupervised storytelling validate qc

# Data center hosting capacity (Module 8, project 2 -- see PROJECTS.md)
datacenters:
	@echo "Module 8 not built yet -- see src/datacenters/README.md"
