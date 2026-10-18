# ERCOT Houston Hub scarcity audit, 2022–2026 (real data)

## Point-in-time boundary — read first

Everything in this audit is **explanatory**. RT prices, SCED reserves (RTOLCAP, PRC), price adders
(RTORPA, RTORDPA, RTRDPA) and System Lambda are realized outcomes published after the operating
interval. They explain why historical prices moved; none of them may be used as a feature in a
day-ahead (previous-day 15:00 CPT) forecast. A forecasting study needs separately archived forecast
vintages (load, wind, solar, STSA) with their original publication timestamps.

## Data and quality

| Source | Report | Coverage | Check |
|---|---|---|---|
| RT hub SPP, 15-min | NP6-785-ER (13061) | 2022-01-01 → 2025-12-31 | 140,256 intervals per hub, 0 missing, 0 duplicate UTC starts |
| DAM hub SPP, hourly | NP4-180-ER (13060) | 2022-01-01 → 2025-12-31 | 35,064 hours per hub, 0 missing |
| SCED adders & reserves (old format) | NP6-792-ER (13231) | 2022-01-01 → 2025-12-05 00:00 CST | ~105k SCED runs/year; ends exactly at RTC+B go-live |
| SCED adders (RTC+B format) | NP6-792-ER (13231) | 2025-12-05 → 2026-10-17 | no ORDC adder columns (RTRDPA family instead) |

- DST: local "hour ending" + Repeated Hour Flag converted to UTC interval starts; every hour has 4 RT intervals.
- ERCOT's 2022 adder bundle contains a workbook mis-named `RTM_ORDC_REL_DPLY_PRC_ADDR_RSRV_2023.xlsx`; extract each bundle into its own folder.
- One anomalous SCED run is excluded (flag: RTOLCAP < 20% of both neighbouring runs): 2025-06-30 15:40 CPT,
  RTOLCAP 1,719 MW and RTORPA $4,969 while adjacent runs show ~16,000–19,500 MW and $0; the settled Houston
  15-min price was $30.47, so the adder never reached settlement. It is the only run flagged in 2022–2025.
- SCED runs averaged to 15-min and joined to Houston RT SPP: 137,657 of 137,664 pre-RTC+B intervals matched.

## 1. Spike events collapsed after 2023

Declustered events (runs of 15-min intervals ≥ threshold, new event after a gap > 60 min), HB_HOUSTON:

| threshold | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| ≥ $500 | 66 | 62 | 16 | 6 |
| ≥ $1,000 | 27 | 41 | 12 | 5 |
| ≥ $2,000 | 16 | 28 | 6 | 2 |
| ≥ $4,500 | 4 | 12 | 2 | 0 |
| ≥ $5,000 | 2 | 4 | 0 | 0 |

- Max RT SPP $5,168.62: settlement prices are not hard-capped at HCAP $5,000. Near-cap pile-up exists only in 2022–23.
- Median duration of ≥ $1,000 events: 90 / 60 / 30 / 15 minutes (2022 → 2025); every 2025 event lasted ≤ 30 min.
- 2023 had 24 of its 41 events in August. In 2024–25, events cluster at 18:00–20:00 (solar ramp-down).
- Spikes are system-wide: 78% of Houston ≥ $1,000 intervals had all four hubs ≥ $1,000 (88% with North).
- DA anticipation: 53–54% of ≥ $1,000 RT hours in 2022–23 were among the day's 3 highest DA-price hours (2024: 78%, n=18; 2025: 80%, n=5).
- RT − DA hourly spread, 99.9th percentile: $2,727 / $1,980 / $503 / $194.

## 2. Online reserves rose sharply

| | 2022 | 2023 | 2024 | 2025* |
|---|---|---|---|---|
| RTOLCAP median (MW) | 10,955 | 12,743 | 16,184 | 18,524 |
| RTOLCAP 1st percentile (MW) | 5,175 | 6,097 | 7,684 | 8,740 |
| PRC median (MW) | 5,046 | 6,756 | 9,041 | 11,075 |
| hours with RTOLCAP < 6,000 MW | 308 | 76 | 8 | 0.25 |
| mean RTORPA ($/MWh) | 5.18 | 0.93 | 0.20 | 0.014 |
| 15-min intervals with ORDC+RDPA adder ≥ $100 | 441 | 107 | 23 | 5 |

*2025 through Dec 4 (pre-RTC+B).

## 3. Approximate System Lambda and adder associations (not accounting identity)

Mean decomposition of Houston RT15 ≥ $1,000 intervals ($/MWh):

| year | n | price | System Lambda | ORDC adder | reliability adder | unexplained residual (not identified congestion) |
|---|---|---|---|---|---|---|
| 2022 | 174 | 2,301 | 1,365 | 442 | 186 | 308 |
| 2023 | 248 | 2,644 | 2,473 | 68 | 49 | 54 |
| 2024 | 31 | 2,334 | 2,282 | 105 | 0 | −53 |
| 2025 | 7 | 1,929 | 1,894 | 0 | 3 | 32 |

System Lambda is ≥ 50% of the price in 77% of spike intervals; ORDC+RDPA adder in only 13%.
Spring 2022 has a cluster of Houston-local spikes with ample reserves and large unexplained residuals; these residuals must not be identified as congestion without settlement-rule reconstruction.
Implication: ORDC alone is insufficient to account for recent extreme settlement prices; the relevant structure is
an interplay of reserves, energy offers and settlement pricing.

## 4. Spike probability by reserve level

Pooled 2022–2025, P(Houston RT15 ≥ $1,000 | RTOLCAP bin):

| RTOLCAP | <4k | 4–5k | 5–6k | 6–8k | 8–10k | >10k |
|---|---|---|---|---|---|---|
| P(spike) | 100% | 32% | 5.9% | 1.6% | 0.37% | 0.03% |

The curve is steep but not stable: at 6–8k MW the rate was 0.4% in 2022 vs 4.1% in 2023.
Counterfactual (2022–23 pooled rates by finer reserve bin × each year's reserve mix):

| year | actual spike intervals | expected from reserve mix |
|---|---|---|
| 2022 | 174 | 302 |
| 2023 | 248 | 120 |
| 2024 | 31 | 35 |
| 2025 | 7 | 16 |

Fewer tight-reserve hours are consistent with most of the 2024–25 collapse, but the conditional curve itself
moves year to year, so a fixed reserve→spike curve is not a reliable forecasting model.

## 5. Post-RTC+B glimpse

System Lambda, SCED runs, Jan 1 – Oct 17 of each year:

| | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| λ ≥ $1,000 | 213 | 769 | 89 | 33 | 9 |
| λ ≥ $2,000 | 108 | 484 | 42 | 14 | 0 |
| max λ | 5,001 | 5,001 | 5,001 | 4,992 | 1,373 |

One post-RTC+B year with no attribution: weather, new capacity and the market redesign all differ.
Post-RTC+B RTRDPA is a different construct from pre-RTC+B RTORPA and is not compared directly.

## 6. Net load, storage and reserves (descriptive)

Sources: ERCOT Fuel Mix Report (IntGenbyFuel 2022–2026, 15-min MWh by fuel) and Native Load archives
(hourly, 2022–2026). Both cover 2022-01-01 → 2026-09-30, 41,615 aligned hours, no gaps; generation/load
ratio 0.997–1.000 each year. Net load = native load − wind − solar. WSL is storage charging load. Fuel Mix "Other" is not labelled as storage by ERCOT, so it was tested
(`scripts/validate_storage_proxy.py`, `results/netload/storage_proxy_validation.*`):

| | 2022 | 2023 | 2024 | 2025 | 2026 (Jan–Sep) |
|---|---|---|---|---|---|
| `Other` energy (TWh) | 0.57 | 0.84 | 2.33 | 5.54 | 6.98 |
| storage charging energy (TWh) | 0.67 | 1.04 | 2.81 | 6.68 | 8.24 |
| ratio | 0.86 | 0.81 | 0.83 | 0.83 | 0.85 |

The ratio matches battery round-trip efficiency every year; the 2025 hourly profiles are mirror images (charging peaks
08:00–11:00, `Other` peaks 06:00–07:00 and 17:00–21:00); daily `Other` and charging energy correlate at 0.93 from 2024 on.
`Other` is therefore read as storage discharge below, allowing for a small non-storage component.

Jan–Sep of each year (comparable with 2026):

| | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| mean load (GW) | 50.8 | 52.6 | 53.8 | 57.1 | 60.2 |
| peak net load (GW) | 65.7 | 70.4 | 69.8 | 69.5 | 75.1 |
| solar peak (GW) | 10.2 | 13.8 | 21.9 | 29.6 | 35.1 |
| storage discharge (`Other`) peak (GW) | 0.7 | 1.6 | 3.4 | 7.0 | 11.9 |
| storage discharge (`Other`), 18–20h mean (GW) | 0.1 | 0.2 | 0.7 | 2.2 | 4.1 |

The 100 highest net-load hours of each Jan–Sep:

| | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| net load (GW) | 62.9 | 66.0 | 63.4 | 63.6 | 67.8 |
| storage discharge (`Other`) (GW) | 0.2 | 0.4 | 1.0 | 3.6 | 7.3 |
| online reserve RTOLCAP (GW) | 5.9 | 6.9 | 9.7 | 10.8 | n/a |
| Houston spike hours | 29 | 67 | 4 | 0 | 0 |
| median hour (CPT) | 16 | 18 | 19 | 19 | 20 |

Online reserve at a fixed net load (linear fit of hourly RTOLCAP on net load, hours ≥ 45 GW, full years):
7.8 / 10.2 / 11.2 / 13.3 GW at 55 GW net load (2022 → 2025).

- Demand did not fall: load grew every year and peak net load in 2026 is the highest in the sample.
- At 55 GW net load the fitted online reserve is ~5.5 GW higher in 2025 than in 2022, while demand kept growing: the change is on the supply side of the balance.
- Storage discharge in the tightest hours rose from 0.2 GW (2022) to 3.6 GW (2025) and 7.3 GW (2026). It does not explain the 2022 → 2023 reserve step (+2.4 GW at 55 GW, storage +0.04 GW), which remains unexplained here.
- Discharge is a lower bound on storage's contribution to online reserve, since idle battery headroom also counts.
- These are associations: outages, thermal fleet changes, interconnection, reserve-definition changes and weather are not controlled, so the share of the reserve increase caused by storage is not estimated.
- The tightest hours moved to 19:00–20:00 as solar grew, which is when storage discharge peaks.
- Remaining spikes are not system-tightness events: 2022–23 spike hours sat at the 98–99th net-load percentile,
  2024–25 spike hours at the 86–88th, with 2025 spike-hour reserves averaging 12.2 GW.
- 2026 (post-RTC+B) had the tightest net load in the sample, 7.3 GW of storage in those hours, no Houston-spike-level
  System Lambda (max $1,373). Storage growth and RTC+B both changed between 2025 and 2026, so the two cannot be separated with this data.

## 7. Battery energy-arbitrage value: the tail disappeared

Daily TB2 = mean of the 2 highest hourly prices minus the 2 lowest ($/MWh); **TB2 is a price spread, not revenue**. The separate chronological energy-only estimate optimizes hourly charge and discharge at 1 MW / 2 MWh, 85% round-trip efficiency, 0.125 MWh SOC increments, perfect foresight, and zero initial / ending SOC each local operating day. This is an **ex-post opportunity**, not achieved revenue or a tradable backtest.

| | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|
| RT chronological opportunity ($k / MW-year) | 125.5 | 148.6 | 56.1 | 44.0 |
| DA chronological opportunity ($k / MW-year) | 87.1 | 134.0 | 51.5 | 38.3 |
| RT TB2 median ($/MWh) | 57.9 | 44.6 | 37.5 | 45.2 |
| Share of RT opportunity in 10 best days | 40.1% | 45.4% | 36.5% | 17.1% |
| Share on RT spike days (hourly max ≥ $1,000) | 51.8% | 67.0% | 26.7% | 7.7% |

- RT chronological opportunity declined **70.4%** from 2023 to 2025, while typical daily TB2 moved much less. The upper tail is a major driver of the change.
- This is consistent with the economic **hypothesis** of storage revenue cannibalization, but the price/dispatch evidence alone cannot attribute the decline to battery additions.
- No ancillary services, trading costs, degradation, price impact or inter-day SOC optimization are included.

## Not yet covered

- 2026 RT settlement prices (no annual NP6-785-ER file until January 2027; daily reports needed).
- Installed battery capacity by month (would separate storage headroom from discharge).
- Any point-in-time forecasting study (see boundary above).

## Reproduce

```bash
python scripts/import_ercot_archive.py --raw data/raw --out data/processed
python scripts/run_price_audit.py --proc data/processed --out results/real_audit
python scripts/import_ercot_adders.py --xlsx <bundle>.xlsx --out data/processed/adders_<year>.csv   # per file
python scripts/analyze_adders.py --proc data/processed --out results/adders
python scripts/import_ercot_fuelmix_load.py --fuel-dir data/raw/fuelmix --load-dir data/raw/load --out data/processed
python scripts/analyze_netload.py --proc data/processed --adders results/adders --out results/netload
python scripts/analyze_battery_spreads.py --proc data/processed --out results/battery
```
Post-RTC+B adder files go to `adders_post_2025.csv` and `adders_post_2026.csv`.


## Public-release methodology note

The SCED subtraction `SPP - System Lambda - price adders` is **not** an exact ERCOT settlement identity. Its residual is not proved to be congestion. Fuel Mix `Other` is validated against storage charging as storage discharge (section 6), but correlations with reserves still cannot establish the causal share of the reserve increase due to batteries. Battery valuations in `results/battery` were recomputed with daily chronological SOC optimization; earlier values from a sign-dependent TB2 efficiency formula were superseded. See `docs/REPRODUCIBILITY.md`.
