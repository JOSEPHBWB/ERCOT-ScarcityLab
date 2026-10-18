"""Explain ERCOT Houston Hub RT spikes with SCED reserves and price adders, 2022-2026.

Explanatory analysis only: reserves, adders and System Lambda are realized SCED
outcomes and are NOT point-in-time features for a day-ahead forecast.

Inputs (from import_ercot_archive.py / import_ercot_adders.py):
  <proc>/rt15_HB_HOUSTON.csv, <proc>/adders_<year>.csv (2022-2025, pre-RTC+B),
  <proc>/adders_post_2025.csv, <proc>/adders_post_2026.csv (post-RTC+B)
Usage:
  python analyze_adders.py --proc data/processed --out results/adders
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_ercot_adders import flag_anomalies  # noqa: E402

ZONE = "America/Chicago"
SPIKE = 1000.0
COLS = ["System Lamda", "RTORPA", "RTORDPA", "RTOLCAP", "PRC"]


def read_adders(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d["sced_utc"] = pd.to_datetime(d["sced_utc"], utc=True, format="ISO8601")
    return flag_anomalies(d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    proc, out = Path(a.proc), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report: list[str] = []

    pre = pd.concat([read_adders(proc / f"adders_{y}.csv") for y in (2022, 2023, 2024, 2025)])
    flagged = pre[pre.anomaly_flag]
    report.append(f"Anomalous SCED runs excluded: {len(flagged)}")
    report.append(flagged.assign(t=flagged.sced_utc.dt.tz_convert(ZONE))[
        ["t", "System Lamda", "RTORPA", "RTOLCAP"]].to_string(index=False))
    pre = pre[~pre.anomaly_flag]

    pre["start"] = pre.sced_utc.dt.floor("15min")
    q = pre.groupby("start")[COLS].mean().reset_index()
    rt = pd.read_csv(proc / "rt15_HB_HOUSTON.csv")
    rt["start"] = pd.to_datetime(rt["start"], utc=True, format="ISO8601")
    m = rt[["start", "price"]].merge(q, on="start", how="inner")
    m["year"] = m.start.dt.tz_convert(ZONE).dt.year
    m["adder"] = m.RTORPA + m.RTORDPA
    m["residual"] = m.price - m["System Lamda"] - m.adder
    m["spike"] = (m.price >= SPIKE).astype(int)
    m.to_csv(out / "houston_rt15_with_adders_2022_2025.csv", index=False)

    g = m.groupby("year")
    annual = pd.DataFrame({
        "RTOLCAP_median": g.RTOLCAP.median(), "RTOLCAP_p1": g.RTOLCAP.quantile(.01),
        "PRC_median": g.PRC.median(), "mean_RTORPA": g.RTORPA.mean(),
        "hours_RTOLCAP_lt_6000": g.RTOLCAP.apply(lambda x: (x < 6000).sum() / 4),
        "intervals_adder_ge_100": g.adder.apply(lambda x: (x >= 100).sum()),
        "spike_intervals": g.spike.sum()})
    annual.round(3).to_csv(out / "annual_reserves_adders.csv")
    report += ["", "== Annual reserves and adders", annual.round(3).to_string()]

    s = m[m.spike == 1]
    decomp = s.groupby("year").agg(n=("price", "size"), price=("price", "mean"),
                                   system_lambda=("System Lamda", "mean"),
                                   ordc_adder=("RTORPA", "mean"), reliability_adder=("RTORDPA", "mean"),
                                   residual=("residual", "mean")).round(0)
    decomp.to_csv(out / "spike_decomposition.csv")
    report += ["", "== Spike decomposition ($/MWh, mean over RT15 >= $1,000)", decomp.to_string(),
               f"lambda >= 50% of price: {((s['System Lamda'] / s.price) >= .5).mean():.2f}",
               f"adder  >= 50% of price: {((s.adder / s.price) >= .5).mean():.2f}"]

    edges = [0, 4000, 5000, 6000, 8000, 10000, 1e9]
    labels = ["<4k", "4-5k", "5-6k", "6-8k", "8-10k", ">10k"]
    m["bin"] = pd.cut(m.RTOLCAP, edges, labels=labels)
    hits = pd.crosstab(m.year, m.bin, values=m.spike, aggfunc="sum").fillna(0).astype(int)
    n = pd.crosstab(m.year, m.bin)
    cond = (m.groupby("bin", observed=False).spike.mean() * 100).round(2)
    (hits.astype(str) + " / " + n.astype(str)).to_csv(out / "spikes_by_reserve_bin.csv")
    report += ["", "== Spike intervals / intervals by RTOLCAP bin", (hits.astype(str) + " / " + n.astype(str)).to_string(),
               "", "== Pooled P(spike | bin) %", cond.to_string()]

    fine = [0, 5000, 6000, 7000, 8000, 9000, 10000, 12000, 15000, 20000, 1e9]
    m["fbin"] = pd.cut(m.RTOLCAP, fine)
    rate = m[m.year <= 2023].groupby("fbin", observed=False).spike.mean().fillna(0)
    rows = []
    for y, gy in m.groupby("year"):
        mix = gy.fbin.value_counts().reindex(rate.index).fillna(0)
        rows.append({"year": y, "actual": int(gy.spike.sum()), "expected_from_reserve_mix": round(float((mix * rate).sum()), 1)})
    shift = pd.DataFrame(rows)
    shift.to_csv(out / "shift_share.csv", index=False)
    report += ["", "== Counterfactual: 2022-23 rates by reserve bin x each year's reserve mix", shift.to_string(index=False)]

    lam = pd.concat([pre[["sced_utc", "System Lamda"]],
                     read_adders(proc / "adders_post_2025.csv")[["sced_utc", "System Lamda"]],
                     read_adders(proc / "adders_post_2026.csv")[["sced_utc", "System Lamda"]]])
    t = lam.sced_utc.dt.tz_convert(ZONE)
    win = lam[(t.dt.month < 10) | ((t.dt.month == 10) & (t.dt.day <= 17))]
    yr = win.sced_utc.dt.tz_convert(ZONE).dt.year
    lam_tab = win.groupby(yr)["System Lamda"].agg(
        n="size", ge1000=lambda x: (x >= 1000).sum(), ge2000=lambda x: (x >= 2000).sum(), max="max").round(1)
    lam_tab.to_csv(out / "system_lambda_jan_oct17.csv")
    report += ["", "== System Lambda, SCED runs Jan 1 - Oct 17", lam_tab.to_string()]

    (out / "analysis_report.txt").write_text("\n".join(report))
    print("\n".join(report))
    plot(m, lam_tab, out)


def plot(m: pd.DataFrame, lam_tab: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#bbbab5", "axes.labelcolor": "#52514e",
                         "xtick.color": "#52514e", "ytick.color": "#52514e"})
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6), facecolor="#fcfcfb")
    for ax in (a, b):
        ax.set_facecolor("#fcfcfb")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", lw=.8)
        ax.set_axisbelow(True)
    years = sorted(m.year.unique())
    specs = [("< 6,000 MW", lambda x: x < 6000, "#104281"),
             ("6,000–8,000 MW", lambda x: (x >= 6000) & (x < 8000), "#2a78d6"),
             ("8,000–10,000 MW", lambda x: (x >= 8000) & (x < 10000), "#86b6ef")]
    for i, (lab, f, c) in enumerate(specs):
        v = [f(m[m.year == y].RTOLCAP).sum() / 4 for y in years]
        x = np.arange(len(years)) + (i - 1) * .28
        a.bar(x, v, .26, color=c, label=lab, edgecolor="#fcfcfb", linewidth=2)
        for xx, vv in zip(x, v):
            a.text(xx, vv + 20, f"{vv:,.0f}", ha="center", va="bottom", fontsize=8, color="#52514e")
    a.set_xticks(range(len(years)), [str(y) for y in years])
    a.set_ylabel("Hours per year")
    a.set_title("Hours with tight online reserves", loc="left", fontsize=11.5, fontweight="bold", color="#0b0b0b")
    a.legend(frameon=False, fontsize=9, title="RTOLCAP", title_fontsize=9)
    ly = [str(y) for y in lam_tab.index]
    v = lam_tab["ge1000"].tolist()
    b.bar(ly, v, .55, color=["#eb6834" if y == "2026" else "#2a78d6" for y in ly], edgecolor="#fcfcfb", linewidth=2)
    for i, vv in enumerate(v):
        b.text(i, vv + 10, str(int(vv)), ha="center", va="bottom", fontsize=9, color="#52514e")
    if "2026" in ly:
        b.text(ly.index("2026"), v[ly.index("2026")] + max(v) * .09,
               f"post-RTC+B\nmax λ = ${lam_tab.loc[2026, 'max']:,.0f}", ha="center", fontsize=8.5, color="#52514e")
    b.set_ylabel("SCED runs with System Lambda ≥ $1,000")
    b.set_title("Energy-price scarcity, Jan 1 – Oct 17 each year", loc="left", fontsize=11.5, fontweight="bold", color="#0b0b0b")
    fig.text(.01, .01, "Source: ERCOT NP6-792-ER historical SCED price adders & reserves (2022–2026), NP6-785-ER RT hub prices. "
             "RTOLCAP = real-time online reserve capacity, 15-min means; 2025 reserves through Dec 4.", fontsize=8, color="#52514e")
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(out / "ercot_reserves_and_lambda_2022_2026.png", dpi=180, facecolor="#fcfcfb")


if __name__ == "__main__":
    main()
