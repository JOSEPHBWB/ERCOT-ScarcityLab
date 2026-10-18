"""Import ERCOT historical annual hub/load-zone price archives.

Sources (official ERCOT bundled reports):
  NP6-785-ER  (report type 13061)  RTMLZHBSPP_<year>.xlsx  15-minute RT SPP
  NP4-180-ER  (report type 13060)  DAMLZHBSPP_<year>.xlsx  hourly DAM SPP

Each workbook has one sheet per month. ERCOT labels time as local
(America/Chicago) "hour ending" with a Repeated Hour Flag for the fall-back
DST hour. We convert every interval to a UTC interval start.

Usage:
  python import_ercot_archive.py --raw data/raw --out data/processed [--hubs HB_HOUSTON HB_NORTH]
Writes rt15_<hub>.csv and da_<hub>.csv with columns start,end,price (UTC),
which is the format week1_audit.audit() expects.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd

ZONE = "America/Chicago"


def _read_workbook(path: str) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return pd.concat(sheets.values(), ignore_index=True)


def _localize(naive: pd.Series, repeated_flag: pd.Series) -> pd.Series:
    """Local wall-clock interval start -> UTC.

    In the repeated fall-back hour, flag 'N' is the first pass (CDT) and
    'Y' is the second pass (CST). A nonexistent spring-forward time raises.
    """
    first_pass = repeated_flag.astype(str).str.upper().eq("N").to_numpy()
    local = pd.DatetimeIndex(naive).tz_localize(
        ZONE, ambiguous=first_pass, nonexistent="raise")
    return pd.Series(local.tz_convert("UTC"), index=naive.index)


def load_rt(path: str, hubs: list[str]) -> pd.DataFrame:
    df = _read_workbook(path)
    df = df[df["Settlement Point Name"].isin(hubs)].copy()
    date = pd.to_datetime(df["Delivery Date"], format="%m/%d/%Y")
    hour_ending = df["Delivery Hour"].astype(int)
    interval = df["Delivery Interval"].astype(int)
    naive = (date + pd.to_timedelta(hour_ending - 1, unit="h")
             + pd.to_timedelta((interval - 1) * 15, unit="min"))
    df["start"] = _localize(naive, df["Repeated Hour Flag"])
    df["end"] = df["start"] + pd.Timedelta(minutes=15)
    df["price"] = pd.to_numeric(df["Settlement Point Price"], errors="raise")
    df["hub"] = df["Settlement Point Name"]
    return df[["hub", "start", "end", "price"]]


def load_da(path: str, hubs: list[str]) -> pd.DataFrame:
    df = _read_workbook(path)
    df = df[df["Settlement Point"].isin(hubs)].copy()
    date = pd.to_datetime(df["Delivery Date"], format="%m/%d/%Y")
    hour_ending = df["Hour Ending"].astype(str).str.slice(0, 2).astype(int)
    naive = date + pd.to_timedelta(hour_ending - 1, unit="h")
    df["start"] = _localize(naive, df["Repeated Hour Flag"])
    df["end"] = df["start"] + pd.Timedelta(hours=1)
    df["price"] = pd.to_numeric(df["Settlement Point Price"], errors="raise")
    df["hub"] = df["Settlement Point"]
    return df[["hub", "start", "end", "price"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hubs", nargs="+", default=["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"files": [], "checks": {}}
    for kind, pattern, loader in [("rt15", "*RTMLZHBSPP_*.xlsx", load_rt),
                                  ("da", "*DAMLZHBSPP_*.xlsx", load_da)]:
        files = sorted(glob.glob(str(Path(a.raw) / pattern)))
        if not files:
            raise FileNotFoundError(f"No {pattern} in {a.raw}")
        frames = []
        for f in files:
            print("reading", Path(f).name, flush=True)
            frames.append(loader(f, a.hubs))
            manifest["files"].append(Path(f).name)
        allp = pd.concat(frames, ignore_index=True).sort_values(["hub", "start"])
        for hub, g in allp.groupby("hub"):
            dup = int(g["start"].duplicated().sum())
            step = pd.Timedelta(minutes=15) if kind == "rt15" else pd.Timedelta(hours=1)
            span = (g["start"].max() - g["start"].min()).total_seconds()
            expected = int(span // step.total_seconds()) + 1
            manifest["checks"][f"{kind}_{hub}"] = {
                "rows": len(g), "duplicate_utc_starts": dup,
                "expected_rows_if_complete": expected,
                "missing_rows": expected - g["start"].nunique(),
                "first_start_utc": str(g["start"].min()),
                "last_start_utc": str(g["start"].max())}
            if dup:
                raise ValueError(f"{kind} {hub}: {dup} duplicate UTC starts")
            g[["start", "end", "price"]].to_csv(out / f"{kind}_{hub}.csv", index=False)
    (out / "import_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["checks"], indent=2))


if __name__ == "__main__":
    main()
