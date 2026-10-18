"""Where did ERCOT's extra reserves come from? Net load, storage and reserves, 2022-2026.

Explanatory only (realized outcomes, not point-in-time forecast features).
Inputs: <proc>/fuelmix_hourly.csv, <proc>/load_hourly.csv (import_ercot_fuelmix_load.py)
        <adders>/houston_rt15_with_adders_2022_2025.csv (analyze_adders.py)
Usage:
  python analyze_netload.py --proc data/processed --adders results/adders --out results/netload
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ZONE = "America/Chicago"
FUELS = ["Biomass", "Coal", "Gas", "Gas-CC", "Hydro", "Nuclear", "Other", "Solar", "Wind"]


def build(proc: Path, adders: Path) -> pd.DataFrame:
    f = pd.read_csv(proc / "fuelmix_hourly.csv")
    l = pd.read_csv(proc / "load_hourly.csv")
    for d in (f, l):
        d["hour_utc"] = pd.to_datetime(d["hour_utc"], utc=True, format="ISO8601")
    h = l.merge(f, on="hour_utc")
    loc = h.hour_utc.dt.tz_convert(ZONE)
    h["year"], h["hr"], h["month"] = loc.dt.year, loc.dt.hour, loc.dt.month
    h["net_load"] = h.load_mw - h.Wind - h.Solar
    h["storage_dis"] = h.Other           # proxy: ERCOT reports ESR discharge under "Other"
    h["storage_chg"] = -h.WSL
    h["gen_minus_load"] = h[FUELS].sum(axis=1) + h.WSL - h.load_mw
    m = pd.read_csv(adders / "houston_rt15_with_adders_2022_2025.csv")
    m["hour_utc"] = pd.to_datetime(m.start, utc=True, format="ISO8601").dt.floor("h")
    mh = m.groupby("hour_utc").agg(RTOLCAP=("RTOLCAP", "mean"), rt_max=("price", "max")).reset_index()
    h = h.merge(mh, on="hour_utc", how="left")
    h["spike"] = h.rt_max >= 1000
    return h


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc", required=True)
    ap.add_argument("--adders", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    h = build(Path(a.proc), Path(a.adders))
    rep = [f"gen/load ratio by year: {(1 + h.groupby('year').gen_minus_load.sum() / h.groupby('year').load_mw.sum()).round(3).to_dict()}"]

    js = h[h.month <= 9]                                   # Jan-Sep: comparable with 2026
    g = js.groupby("year")
    eve = js[js.hr.isin([18, 19, 20])].groupby("year")
    annual = pd.DataFrame({
        "load_mean": g.load_mw.mean(), "load_peak": g.load_mw.max(),
        "netload_peak": g.net_load.max(), "netload_p99": g.net_load.quantile(.99),
        "wind_mean": g.Wind.mean(), "solar_mean": g.Solar.mean(), "solar_peak": g.Solar.max(),
        "storage_dis_peak": g.storage_dis.max(), "storage_dis_18_20h_mean": eve.storage_dis.mean(),
        "storage_chg_peak": g.storage_chg.max(),
        "gas_peak": (js["Gas"] + js["Gas-CC"]).groupby(js.year).max()}).round(0)
    annual.to_csv(out / "annual_system_jan_sep.csv")
    rep += ["", "== Jan-Sep system summary (MW)", annual.to_string()]

    top = (js.sort_values("net_load", ascending=False).groupby("year").head(100)
           .groupby("year").agg(net_load=("net_load", "mean"), load=("load_mw", "mean"), wind=("Wind", "mean"),
                                solar=("Solar", "mean"), storage_dis=("storage_dis", "mean"),
                                gas_cc=("Gas-CC", "mean"), RTOLCAP=("RTOLCAP", "mean"),
                                spike_hours=("spike", "sum"), median_hour=("hr", "median")).round(0))
    top.to_csv(out / "top100_netload_hours_jan_sep.csv")
    rep += ["", "== Top-100 net-load hours, Jan-Sep (MW)", top.to_string()]

    rows = []
    for y, gy in h[h.year <= 2025].dropna(subset=["RTOLCAP"]).groupby("year"):
        hi = gy[gy.net_load >= 45000]
        b = np.polyfit(hi.net_load, hi.RTOLCAP, 1)
        rows.append({"year": y, "slope": round(b[0], 3), "RTOLCAP_at_55GW": round(np.polyval(b, 55000)),
                     "RTOLCAP_at_60GW": round(np.polyval(b, 60000)), "hours_netload_ge_45GW": len(hi),
                     "storage_dis_mean_those_hours": round(hi.storage_dis.mean())})
    fit = pd.DataFrame(rows)
    fit.to_csv(out / "reserve_at_fixed_netload.csv", index=False)
    rep += ["", "== Hourly RTOLCAP ~ net load (full years, hours with net load >= 45 GW)", fit.to_string(index=False)]

    sp = h[h.spike]
    ctx = sp.groupby("year").agg(n=("spike", "size"), net_load=("net_load", "mean"), storage_dis=("storage_dis", "mean"),
                                 RTOLCAP=("RTOLCAP", "mean")).round(0)
    ctx["netload_pctile_median"] = [round(float(np.median([(h[h.year == y].net_load < v).mean() * 100
                                                           for v in sp[sp.year == y].net_load])), 1) for y in ctx.index]
    ctx.to_csv(out / "spike_hour_context.csv")
    rep += ["", "== Houston spike hours (RT max >= $1,000): system context", ctx.to_string()]
    (out / "netload_report.txt").write_text("\n".join(rep))
    print("\n".join(rep))

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#bbbab5", "axes.labelcolor": "#52514e",
                         "xtick.color": "#52514e", "ytick.color": "#52514e"})
    fig, axs = plt.subplots(1, 3, figsize=(13.5, 4.6), facecolor="#fcfcfb")
    yrs = [str(y) for y in top.index]
    panels = [("Net load stayed high", "Avg net load, top-100 hours (GW)", list(top.net_load / 1000), yrs),
              ("Batteries filled the peak", "Avg storage discharge, same hours (GW)", list(top.storage_dis / 1000), yrs),
              ("Reserves at the same net load", "Online reserve at 55 GW net load (GW)",
               list(fit.RTOLCAP_at_55GW / 1000), [str(y) for y in fit.year])]
    for ax, (title, ylab, vals, xs) in zip(axs, panels):
        ax.set_facecolor("#fcfcfb")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", lw=.8)
        ax.set_axisbelow(True)
        ax.bar(xs, vals, .6, color=["#eb6834" if x == "2026" else "#2a78d6" for x in xs], edgecolor="#fcfcfb", linewidth=2)
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals) * .015, f"{v:.1f}", ha="center", va="bottom", fontsize=9, color="#52514e")
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", color="#0b0b0b")
        ax.set_ylabel(ylab)
    fig.text(.01, .01, "Left/middle: Jan–Sep each year, 100 highest net-load hours (2026 post-RTC+B, orange). Right: full years, "
             "linear fit of hourly RTOLCAP on net load for hours ≥ 45 GW.\nNet load = native load − wind − solar. "
             "Storage discharge = Fuel Mix \"Other\". Sources: ERCOT Fuel Mix Report, Native Load archives, NP6-792-ER.",
             fontsize=8, color="#52514e")
    fig.tight_layout(rect=(0, .07, 1, 1))
    fig.savefig(out / "ercot_netload_storage_reserves.png", dpi=180, facecolor="#fcfcfb")


if __name__ == "__main__":
    main()
