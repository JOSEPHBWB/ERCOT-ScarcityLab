# Reproducing ScarcityLab

## Environment and tests

Use Python 3.10+; execute commands from the repository root.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

The tracked `results/` contain the research results and plots for review. Official ERCOT raw historical workbooks and the large intermediate `data/` directory are **not** redistributed. Without raw sources, a clean checkout cannot regenerate every chart; this is intentional and should not be represented as a one-command complete reproduction.

## Price archives (2022–2025)

Download official yearly ERCOT NP6-785-ER (RTMLZHBSPP) and NP4-180-ER (DAMLZHBSPP) bundles, extract year workbooks into `data/raw/`, then:

```bash
python scripts/import_ercot_archive.py --raw data/raw --out data/processed
python scripts/run_price_audit.py --proc data/processed --out results/real_audit
python scripts/analyze_battery_spreads.py --proc data/processed --out results/battery
```

The importer produces `data/processed/rt15_HB_HOUSTON.csv` and `da_HB_HOUSTON.csv`, with UTC interval starts and settlement prices. The battery script groups RT to hourly **mean** prices, preserves each local operating day (including 23/25-hour DST days), and optimizes dispatch sequentially within each day.

For a partial, verified price-only reproduction using a previously exported processed **hourly** Houston table with columns `hour_utc,rt_mean,da`, map its two price columns into separate `start,price` CSVs in `data/processed/`, then run the battery script. This was how the 2022–2025 battery tables were checked during the public-release audit.

## SCED, fuel mix and load

Extract the annual SCED/adder xlsx and fuel/load archives from the official datasets referenced in `docs/OFFICIAL_DATA_PRODUCTS.md`.

```bash
# Repeat for EACH pre- and post-RTC+B SCED workbook, choosing an appropriate filename:
python scripts/import_ercot_adders.py --xlsx path/to/annual.xlsx --out data/processed/adders_2022.csv
python scripts/analyze_adders.py --proc data/processed --out results/adders
python scripts/import_ercot_fuelmix_load.py --fuel-dir data/raw/fuelmix --load-dir data/raw/load --out data/processed
python scripts/analyze_netload.py --proc data/processed --adders results/adders --out results/netload
python scripts/validate_storage_proxy.py --proc data/processed --out results/netload
```

Name SCED outputs `adders_2022.csv` to `adders_2025.csv`, and separately `adders_post_2025.csv` and `adders_post_2026.csv` for the RTC+B schema. ERCOT's archived 2022 workbook contains a misleading year in its filename: inspect the records instead of trusting just the basename.

The SCED filter flags unusually low reserve observations relative to both neighboring runs. Treat them as suspected data anomalies; before exclusion check local settlement prices and report sensitivity to inclusion. Changes in the reserve/adder definition at RTC+B must be kept separate.

## Interpreting results

- The price-adder subtraction is a **heuristic diagnostic**, not an exact price-formation decomposition.
- `Other` fuel-mix output is not labelled as storage by ERCOT; `validate_storage_proxy.py` shows it behaves as storage discharge (discharge/charge energy 0.81–0.86, daily correlation 0.93). It supports describing storage output, not causal attribution of the reserve increase.
- Fixed-net-load comparisons are descriptive regression associations, not estimates of capacity added by batteries.
- SCED reserve, adder and System Lambda are **realized** and cannot be used as previous-day forecast features.
- The chronological battery optimization is an **ex-post daily dispatch benchmark**, not real trading P&L. SOC discretization is 0.125 MWh; it resets to zero daily.

For every derived statistic, distinguish year coverage, exact denominator, MW vs MWh and USD/MWh vs USD/MW-year.

## One command per stage (v2.1)

After the official raw data have been imported into `data/processed/` following the instructions above:

```bash
python scripts/run_all.py --stage prices --proc data/processed --out results/recomputed
python scripts/verify_results.py --out results/recomputed --reference results
```

For the complete analysis, when all SCED, fuel-mix, and load processed inputs are ready:

```bash
python scripts/run_all.py --stage all --proc data/processed --out results/recomputed
```

`--stage all` requires the imported reserve/adder and load/fuel data; it fails on missing inputs rather than silently mixing previously committed results. The manifest records *source archive hashes* from the author's inputs for provenance. These files are not redistributed. The project can reproduce the price audit and battery analysis from historical prices alone, but a new clone still needs the official inputs and suitable extraction. Results under `results/` were created from the provided historical ERCOT exports; the ability to recreate each SCED/Fuel Mix result from a clean clone remains conditional on those inputs.
