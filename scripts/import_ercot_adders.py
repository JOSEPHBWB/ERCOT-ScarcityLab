"""Import ERCOT NP6-792-ER historical SCED-interval price adders and reserves.

Pre-RTC+B files (RTM_ORDC_REL_DPLY_PRC_ADDR_RSRV_<year>.xlsx) carry the ORDC
online/offline reserve adders (RTORPA, RTOFFPA), reliability deployment adder
(RTORDPA), System Lambda and reserve quantities (RTOLCAP, RTOFFCAP, PRC).
Post-RTC+B files (HIST_RT_SCED_PRC_ADDR_<year>.xlsx) no longer carry ORDC adders.

Point-in-time boundary: every field here (reserves, adders, System Lambda) is
a realized SCED outcome, published after the operating interval. Use it to
explain historical prices, never as a day-ahead forecasting feature.

Note: ERCOT's 2022 bundle contains a workbook mis-named *_2023.xlsx; pass each
year's workbook explicitly rather than trusting the file name.

Usage:
  python import_ercot_adders.py --xlsx path/to/file.xlsx --out out.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

ZONE = "America/Chicago"


def read_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    header_row = raw.index[raw.apply(
        lambda r: r.astype(str).str.contains("SCED Timestamp").any(), axis=1)][0]
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[header_row]]
    return df.dropna(subset=["SCED Timestamp"])


def flag_anomalies(df: pd.DataFrame, drop_ratio: float = 0.2) -> pd.DataFrame:
    """Flag isolated SCED runs whose online reserve collapses vs both neighbours.

    Example caught: 2025-06-30 15:40 CPT, RTOLCAP 1,719 MW and RTORPA $4,969
    while adjacent runs show ~16,000-19,500 MW and $0, and the settled
    Houston 15-min price was $30.47 (the adder never reached settlement).
    Flagged rows are kept in the file but excluded from analysis.
    """
    df = df.sort_values("sced_utc").copy()
    df["anomaly_flag"] = False
    if "RTOLCAP" in df:
        prev_, next_ = df["RTOLCAP"].shift(1), df["RTOLCAP"].shift(-1)
        df["anomaly_flag"] = (df["RTOLCAP"] < drop_ratio * prev_) & (df["RTOLCAP"] < drop_ratio * next_)
    return df


def load(path: str) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl")
    frames = [read_sheet(s) for name, s in sheets.items() if name != "Report Info"]
    df = pd.concat(frames, ignore_index=True)
    ts = pd.to_datetime(df["SCED Timestamp"])
    first_pass = df["Repeated Hour Flag"].astype(str).str.upper().eq("N").to_numpy()
    df["sced_utc"] = (pd.DatetimeIndex(ts).tz_localize(
        ZONE, ambiguous=first_pass, nonexistent="shift_forward").tz_convert("UTC"))
    keep = ["sced_utc"] + [c for c in df.columns if c not in
                           ("SCED Timestamp", "Repeated Hour Flag", "Batch ID", "sced_utc", "nan")]
    out = df[keep].copy()
    for c in keep[1:]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return flag_anomalies(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = load(a.xlsx)
    d.to_csv(a.out, index=False)
    print(a.out, len(d), d.sced_utc.min(), d.sced_utc.max())
