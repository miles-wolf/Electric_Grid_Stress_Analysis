# Module 8: Plugging in a Gigawatt

How many GW of data centers can each grid absorb before it exceeds its record peak, and how much
more if they're flexible? What does each new GW emit?

Regions: PJM, ERCO, TVA, MISO, CISO (EIA-930 hourly). Demand 2019–2025; fuel mix + interchange 2025.

| Step | Script (planned) | What it does |
|---|---|---|
| Data | `pull.py` | 5 regions × demand 2019–2025, fuel + interchange 2025 → `data/processed/datacenters/` |
| A | `hosting_capacity.py` | Sweep flat added load; hours/MWh above record peak; firm + flexible (0.25/0.5/1% curtailment budget) |
| A2 | `hosting_capacity.py --year` | Same sweep with 2022/2023 as the test year (weather robustness) |
| B | `regime_migration.py` | Reclassify days with the **frozen** 2025 classifier (`src/operational_classifier.py`); days moving into Extreme |
| C | `marginal_emissions.py` | Regress Δgeneration by fuel on Δdemand (season × time of day); marginal vs average CO₂/MWh; imports as own bucket |
| D (stretch) | `hourly_matching.py` | Share of hours a solar (+ wind) contract covers a flat 1 GW load |

Full plan and limits: `curait_consulting/personal/job-sprint/datacenter-analysis.md`.
