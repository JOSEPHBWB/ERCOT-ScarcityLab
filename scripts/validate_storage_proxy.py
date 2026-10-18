"""Check whether ERCOT Fuel Mix "Other" behaves like energy-storage discharge.

If "Other" is essentially battery discharge, then against WSL (wholesale storage
charging load) it should show:
  1. annual discharge / charge energy close to a battery round-trip efficiency (~0.80-0.90);
  2. a mirror-image daily profile (charge midday/overnight, discharge at morning/evening peaks);
  3. high day-to-day correlation between discharge and charging energy.

Input: <proc>/fuelmix_hourly.csv from import_ercot_fuelmix_load.py
Usage: python scripts/validate_storage_proxy.py --proc data/processed --out results/netload
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ZONE = "America/Chicago"


def validate(fuel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    f = fuel.copy()
    t = pd.to_datetime(f["hour_utc"], utc=True, format="ISO8601").dt.tz_convert(ZONE)
    f["year"], f["hour"], f["day"] = t.dt.year, t.dt.hour, t.dt.date
    f["charge"] = -f["WSL"]
    annual = f.groupby("year").agg(other_TWh=("Other", lambda x: x.sum() / 1e6),
                                   charge_TWh=("charge", lambda x: x.sum() / 1e6))
    annual["discharge_over_charge"] = annual.other_TWh / annual.charge_TWh
    last = int(f["year"].max()) - 1 if (f["year"] == f["year"].max()).sum() < 8760 else int(f["year"].max())
    profile = f[f.year == last].groupby("hour")[["Other", "charge"]].mean()
    daily = f[f.year >= 2024].groupby("day")[["Other", "charge"]].sum()
    corr = float(np.corrcoef(daily.Other, daily.charge)[0, 1])
    return annual, profile, corr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    annual, profile, corr = validate(pd.read_csv(Path(a.proc) / "fuelmix_hourly.csv"))
    annual.round(3).to_csv(out / "storage_proxy_validation.csv")
    profile.round(0).to_csv(out / "storage_proxy_hourly_profile.csv")
    txt = ("== Fuel Mix Other vs storage charging (WSL)\n" + annual.round(3).to_string()
           + f"\n\nDaily correlation of Other and charging energy, 2024 onward: {corr:.3f}"
           + "\n\n== Mean hourly profile, last full year (MW)\n" + profile.round(0).T.to_string())
    (out / "storage_proxy_validation.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
