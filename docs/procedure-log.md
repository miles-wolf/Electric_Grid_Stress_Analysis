# Procedure log

Write a row for every step as you do it, not afterwards. After the project, sort the rows:
repeated **mechanical** steps become agent tools; **judgment** steps become things the agent
*suggests* and a human decides; **one-off** steps stay manual.

Kind: `mech` (same every time, could be code) · `judg` (needed a decision) · `once` (specific to this data)

| Date | Project | Step | What I did | Kind | Time | Tool / script | Could an agent do it? Notes |
|---|---|---|---|---|---|---|---|
| 2026-10-16 | datacenters | Data pull | _example_: downloaded EIA-930 for 5 BAs, 2019–2025 | mech | 1h | `src/datacenters/pull.py` | Yes, given BA list + years |
| | | | | | | | |
