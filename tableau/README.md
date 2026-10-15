# Tableau port of the Grid Stress dashboard

Faithful 1:1 migration of the finished 3-page Power BI dashboard to Tableau.

| File / folder | What it is |
|---|---|
| **`BUILD-GUIDE.md`** | The master guide — data sources, parameters, every DAX→Tableau calc translation (number-matched to the live dashboard), and page-by-page worksheet + dashboard build steps. **Start here.** |
| **`Grid-Stress-Analysis.twb`** | Starter workbook: the 7 data connections, 3 parameters, and all ~29 calculated fields **pre-defined** so you skip the typing. Build the viz layout on top of it per the guide. |
| `data/` | 7 Tableau-ready CSVs (copies of the pipeline outputs). |
| `_build_twb.py` | Regenerates the `.twb` from the CSVs + calc definitions (re-run if data columns change). |

## About the `.twb`
It was authored as XML and validated for well-formedness, but **it has not been opened
in Tableau Desktop** (no Tableau on the build machine). Expect possibly minor fixups on
first open:
- If the CSV connections don't auto-resolve, re-point them to `tableau/data/` (paths are
  currently absolute to this repo).
- Spot-check the calculated fields against `BUILD-GUIDE.md` §3 — every formula there is
  verified against the live dashboard numbers.

If anything in the `.twb` misbehaves, the guide alone is enough to rebuild everything
from a blank workbook.
