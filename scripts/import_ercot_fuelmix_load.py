"""Import ERCOT Fuel Mix (IntGenbyFuel<year>.xlsx) and Native Load (Native_Load_<year>.xlsx).

Fuel Mix: one sheet per month, one row per (Date, Fuel), 96 columns of 15-min
energy (MWh) labelled by interval ending ("0:15" ... "0:00"); the fall-back day
adds four "(DST)" columns. Values are converted to average MW (x4).
Fuels: Biomass, Coal, Gas, Gas-CC, Hydro, Nuclear, Other, Solar, WSL, Wind.
  WSL   = wholesale storage load (battery charging, negative).
  Other = mostly energy storage discharge in recent years (ERCOT reports
          ESR output under "Other"); treat it as a proxy, not a pure battery series.
Native Load: hourly, "Hour Ending" local time (+ " DST" suffix on the repeated
fall-back hour), weather-zone columns and system total "ERCOT" (MW).

DST: "(DST)"-labelled repeated intervals are treated as the second (CST) pass.
This affects one hour per year and nothing in the annual analysis.

Usage:
  python import_ercot_fuelmix_load.py --fuel-dir raw/fuelmix --load-dir raw/load --out processed
Writes fuelmix_hourly.csv (UTC hour start, MW by fuel) and load_hourly.csv.
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ZONE = "America/Chicago"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _to_utc(naive_start: pd.Series, second_pass: np.ndarray) -> pd.Series:
    local = pd.DatetimeIndex(naive_start).tz_localize(
        ZONE, ambiguous=~second_pass, nonexistent="NaT")
    return pd.Series(local.tz_convert("UTC"), index=naive_start.index)


def load_fuelmix(path: str) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=[m for m in MONTHS], engine="openpyxl")
    frames = []
    for df in sheets.values():
        df.columns = [str(c).strip() for c in df.columns]
        df = df.rename(columns={"Fuel Type": "Fuel"}).dropna(subset=["Date", "Fuel"])
        if df.empty:
            continue
        value_cols = [c for c in df.columns if ":" in c]
        long = df.melt(id_vars=["Date", "Fuel"], value_vars=value_cols,
                       var_name="label", value_name="mwh").dropna(subset=["mwh"])
        dst = long["label"].str.contains("DST").to_numpy()
        hhmm = long["label"].str.replace(r"\s*\(DST\)", "", regex=True).str.split(":", expand=True).astype(int)
        minutes = hhmm[0] * 60 + hhmm[1]
        minutes = minutes.where(minutes > 0, 24 * 60)          # "0:00" = end of day
        start_naive = pd.to_datetime(long["Date"]) + pd.to_timedelta(minutes - 15, unit="min")
        long["start"] = _to_utc(start_naive, dst)
        frames.append(long.dropna(subset=["start"]))
    out = pd.concat(frames, ignore_index=True)
    out["mw"] = out["mwh"] * 4
    return out


def load_native(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    # A few cells arrive as Excel datetimes instead of text (e.g. 2022 file); normalise.
    he = df["Hour Ending"].map(
        lambda v: v.strftime("%m/%d/%Y %H:%M") if hasattr(v, "strftime") else str(v)).str.strip()
    dst = he.str.endswith("DST").to_numpy()
    he = he.str.replace(r"\s*DST$", "", regex=True)
    date = pd.to_datetime(he.str.slice(0, 10), format="%m/%d/%Y")
    hour = he.str.slice(11, 13).astype(int)
    start_naive = date + pd.to_timedelta(hour - 1, unit="h")
    df["hour_utc"] = _to_utc(start_naive, dst)
    return df.dropna(subset=["hour_utc"])[["hour_utc", "ERCOT"]].rename(columns={"ERCOT": "load_mw"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuel-dir", required=True)
    ap.add_argument("--load-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    fm = pd.concat([load_fuelmix(f) for f in sorted(glob.glob(f"{a.fuel_dir}/*IntGenbyFuel*.xlsx"))])
    fm["hour_utc"] = fm["start"].dt.floor("h")
    hourly = fm.pivot_table(index="hour_utc", columns="Fuel", values="mw", aggfunc="mean")
    dup = fm.duplicated(["start", "Fuel"]).sum()
    if dup:
        raise ValueError(f"{dup} duplicate fuel-mix intervals")
    hourly.to_csv(out / "fuelmix_hourly.csv")

    ld = pd.concat([load_native(f) for f in sorted(glob.glob(f"{a.load_dir}/Native_Load_*.xlsx"))])
    if ld["hour_utc"].duplicated().any():
        raise ValueError("duplicate load hours")
    ld.sort_values("hour_utc").to_csv(out / "load_hourly.csv", index=False)
    print("fuel-mix hours:", len(hourly), hourly.index.min(), hourly.index.max())
    print("load hours:", len(ld), ld.hour_utc.min(), ld.hour_utc.max())


if __name__ == "__main__":
    main()
