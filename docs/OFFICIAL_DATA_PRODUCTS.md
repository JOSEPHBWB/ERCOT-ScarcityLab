# Official sources and research boundaries

- Historical RT hub/load-zone prices: https://www.ercot.com/mp/data-products/data-product-details?id=NP6-785-ER (report type 13061; listed weekly publication).
- Historical DAM hub/load-zone prices: https://www.ercot.com/mp/data-products/data-product-details?id=NP4-180-ER (report type 13060; listed weekly publication).
- Historical packages may reduce HTTP requests, but their Excel/ZIP schemas and annual coverage must be inspected before writing a bulk importer.
- HCAP changed to $5,000/MWh on January 1, 2022; the OFFER CAP is not an unconditional bound on settlement point prices: https://www.ercot.com/services/comm/mkt_notices/M-A120721-01
- ERCOT real-time cap framework and RTC+B altered market structure. Do NOT code a universal $5,000 SPP clip or an invented official ORDC implementation.
- Daily post-DAM analysis uses assumed 15:00 local decision cut-off; verify actual DAM publication timestamp on each relevant operating day before calling any features point-in-time available.
- All history/vintage source assertions remain unverified until archive manifests and point-in-time posting records are retained.

## Sources used in the empirical study (all downloaded and parsed)
- NP6-785-ER historical RTM hub/load-zone SPP, 2022–2025 (15-min).
- NP4-180-ER historical DAM hub/load-zone SPP, 2022–2025 (hourly).
- NP6-792-ER historical SCED price adders and reserves: RTM_ORDC_REL_DPLY_PRC_ADDR_RSRV_2022–2025 (pre-RTC+B, ends 2025-12-05 00:00 CST) and HIST_RT_SCED_PRC_ADDR_2025/2026 (post-RTC+B, no ORDC adder columns). The 2022 bundle contains a workbook mis-named *_2023.xlsx.
- Fuel Mix Report (IntGenbyFuel2022–2026), https://www.ercot.com/gridinfo/generation — 15-min MWh by fuel; "Other" carries storage discharge, "WSL" storage charging.
- Native Load archives (Native_Load_2022–2026), https://www.ercot.com/gridinfo/load/load_hist — hourly system and weather-zone load.
