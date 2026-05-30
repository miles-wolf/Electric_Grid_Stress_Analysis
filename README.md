# Grid Stress Analysis

**Controls-Inspired Analysis of Variability, Ramping, and Stability in Power Grid Operations**

This project treats Balancing Authorities (BAs) as dynamic systems and analyzes
grid stability using controls-inspired metrics such as ramp rates, variability,
and operating regime identification.

The goal is to demonstrate an end-to-end scientific data workflow including:
- Python-based ETL and analysis
- SQL-based validation and aggregation
- Unsupervised ML (clustering and anomaly detection)
- Clear, interpretable visualizations
- Modular, cloud-ready architecture

Module 1:
- Ingested EIA-930 consolidated operational data (2025 Jan–Dec)
- Filtered to PJM + CAISO (CISO BA code)
- Produced 17,520 hourly records
- QC: 0% missing timestamps; demand missing 0.42% raw / 0.006% adjusted

Module 2:
- Engineered daily BA-level stress features from hourly EIA-930 demand
- Computed hour-to-hour demand ramp metrics (up/down/absolute)
- Added volatility and peak-stress indicators (CV, peak-to-mean, top-hour concentration)
- Normalized stress metrics by system size for PJM vs CAISO comparability
- Added short rolling-window (7-day) z-scores to flag anomalous days
- Produced 732 daily records (365 days × 2 BAs) with coverage tracking

Module 3:
- Defined a daily grid stress score from hourly operational metrics
- Aggregated hourly demand, ramping, and stress indicators to daily features
- Constructed two complementary indices:
  - a z-score–based stress metric capturing statistical extremeness
  - a 0–1 normalized stress metric for intuitive visualization
- Produced exploratory time-series plots and distribution summaries
- Identified seasonal patterns, outliers, and high-risk days
- Daily stress distributions show that PJM experiences elevated operational stress days more frequently, while CAISO typically operates within a narrower baseline range but exhibits pronounced tail-risk outliers.
- Time-series analysis reveals strong seasonal structure in both regions, with broadly comparable baseline variability once extreme events are de-emphasized and differences driven primarily by the frequency and extremeness of high-stress days rather than persistent elevation.

Module 4:
- Applied unsupervised machine learning to identify recurring grid operating regimes
- Constructed daily grid operating-state feature vectors (load, ramping, near-peak persistence, stress)
- Standardized features within balancing authority to remove scale effects
- Applied PCA, with first three components explaining ~94% of variance
- Identified recurring operating regimes using unsupervised K-means clustering
- Found distinct regimes spanning stable operation, sustained stress, high-load stress, and rare extreme events
- Showed that high-stress days emerge as separate regimes rather than as extensions of normal operation
- Quantified regime-specific tail risk, with extreme stress concentrated in rare clusters
- Considered HDBSCAN for rare-state isolation, but PCA + K-means already separated extreme events into distinct regimes; density-based methods remain a future extension.
- Produced PCA visualizations and saved clustered datasets and summary tables for reproducibility

Module 5:
- Visualized operational regimes in feature space using daily peak load and max ramp (z-scores) for CISO and PJM
- Identified distinct regime clusters associated with different operational stress profiles
- Demonstrated that grid stress is regime-dependent rather than driven by single extreme variables
- Compared regime frequency vs. mean stress to distinguish common vs. high-risk operating states
- Analyzed stress events as temporal processes using multi-day windows around high-stress periods
- Showed that stress often lags operational stress and can persist beyond peak load or ramp events
- Observed structural differences between CISO and PJM in regime transitions, ramp behavior, and stress response
- Highlighted both acute (shock-driven) and chronic (sustained-stress) stress events, validating stress as a dynamic state variable rather than a point anomaly
- Grid stress behaves as a regime-dependent, temporally persistent state variable rather than a response to isolated extreme events.

Module 6:
- Synthesized results across data ingestion, feature engineering, and modeling
- Interpreted stress scores as relative operational stress indicators
- Compared PJM and CAISO stress dynamics and variability regimes
- Framed clustering outputs as descriptive grid operating states
- Documented assumptions, limitations, and future extensions


Overall:
Using unsupervised learning, we identified distinct operational regimes in regional power grids based on daily load and ramping behavior and showed that grid stress varies systematically across these regimes. stress was not driven solely by extreme single-day events: instead, we observed multiple pathways to high stress, including shock-driven events with abrupt ramp spikes, regime-bound stress arising from sustained operation in inherently risky states, and accumulated stress events where stress builds gradually over time without clear outliers. Event-level analysis demonstrated that stress dynamics can occur both with and without regime transitions, validating the stress metric as a dynamic systems indicator rather than a proxy for raw load or ramp extremes. Together, these results show how unsupervised ML can reveal interpretable structure in grid behavior and provide context for when and how operational stress translates into systemic stress.

Grid stress and reliability risk are often assessed using single metrics or extreme events, but this analysis shows that stress can emerge through multiple operational pathways, including sustained operation in high-risk regimes without obvious shocks. By identifying regime-dependent and time-persistent stress patterns, this approach provides system operators and planners with earlier warning signals and a framework for targeting mitigation efforts before reliability events occur.
