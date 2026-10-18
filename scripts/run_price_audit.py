"""Houston Hub spike audit from the imported ERCOT price archives (2022-2025).

Reuses week1_audit.audit() (repo root) on the CSVs written by import_ercot_archive.py,
then adds DA-anticipation, RT-DA spread and cross-hub checks plus the audit chart.

Usage:
  python scripts/run_price_audit.py --proc data/processed --out results/real_audit
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from week1_audit import audit  # noqa: E402

ZONE = "America/Chicago"


def read_prices(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    for c in ("start", "end"):
        d[c] = pd.to_datetime(d[c], utc=True, format="ISO8601")
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    proc, out = Path(a.proc), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    rt = read_prices(proc / "rt15_HB_HOUSTON.csv")
    da = read_prices(proc / "da_HB_HOUSTON.csv")
    hourly, counts, events, q = audit(rt, da, None)
    counts.to_csv(out / "annual_spike_counts.csv", index=False)
    events.to_csv(out / "declustered_events.csv", index=False)
    rep = [f"RT intervals {len(rt)}, hours with != 4 intervals: {int((q != 4).sum())}, "
           f"DA hours unmatched: {int(hourly.da_price.isna().sum())}, max RT {rt.price.max():.2f}",
           "", counts.to_string(index=False)]

    loc = hourly.hour_utc.dt.tz_convert(ZONE)
    hourly["day"], hourly["year"] = loc.dt.date, loc.dt.year
    hourly["da_rank"] = hourly.groupby("day").da_price.rank(ascending=False, method="first")
    s = hourly[hourly.rt_max >= 1000]
    rep += ["", "Spike hours (RT max >= $1,000) in the day's top-3 DA hours:",
            s.groupby("year").apply(lambda g: pd.Series({"n": len(g), "in_top3": (g.da_rank <= 3).mean(),
                                                          "da_median": g.da_price.median()}),
                                    include_groups=False).round(2).to_string()]
    hourly["spread"] = hourly.rt_mean - hourly.da_price
    rep += ["", "RT - DA hourly spread:", hourly.groupby("year").spread.agg(
        p999=lambda x: x.quantile(.999), gt250=lambda x: (x > 250).sum(), gt1000=lambda x: (x > 1000).sum()).round(1).to_string()]

    hubs = {}
    for hub in ("HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"):
        p = proc / f"rt15_{hub}.csv"
        if p.exists():
            hubs[hub] = read_prices(p).set_index("start").price
    if len(hubs) == 4:
        H = pd.DataFrame(hubs)
        hit = H[H.HB_HOUSTON >= 1000]
        rep += ["", f"Houston RT15 >= $1,000 intervals with all four hubs >= $1,000: {(hit.min(axis=1) >= 1000).mean():.2f}"]
    (out / "price_audit_report.txt").write_text("\n".join(rep))
    print("\n".join(rep))

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#bbbab5", "axes.labelcolor": "#52514e",
                         "xtick.color": "#52514e", "ytick.color": "#52514e"})
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, 4.6), facecolor="#fcfcfb", gridspec_kw={"width_ratios": [1.1, 1]})
    for x in (ax, bx):
        x.set_facecolor("#fcfcfb")
        x.spines[["top", "right"]].set_visible(False)
        x.grid(axis="y", color="#e6e5e0", lw=.8)
        x.set_axisbelow(True)
    years = sorted(counts.year.unique())
    for i, (u, col) in enumerate(zip((500, 1000, 2000), ("#86b6ef", "#2a78d6", "#104281"))):
        v = [int(counts[(counts.year == y) & (counts.threshold == u)].declustered_events.iloc[0]) for y in years]
        xs = np.arange(len(years)) + (i - 1) * .28
        ax.bar(xs, v, .26, color=col, label=f"≥ ${u:,}", edgecolor="#fcfcfb", linewidth=2)
        for xx, vv in zip(xs, v):
            ax.text(xx, vv + 1, str(vv), ha="center", va="bottom", fontsize=8.5, color="#52514e")
    ax.set_xticks(range(len(years)), [str(y) for y in years])
    ax.set_ylabel("Independent spike events (60-min declustering)")
    ax.set_title("Houston Hub RT spike events collapsed after 2023", loc="left", fontsize=11.5, fontweight="bold", color="#0b0b0b")
    ax.legend(frameon=False, title="15-min RT SPP", title_fontsize=9, fontsize=9)
    e = events[events.threshold == 1000].copy()
    el = pd.to_datetime(e.first_interval, utc=True).dt.tz_convert(ZONE)
    e["hr"], e["era"] = el.dt.hour, np.where(el.dt.year <= 2023, "2022–23", "2024–25")
    for era, col, off in (("2022–23", "#2a78d6", -.21), ("2024–25", "#eb6834", .21)):
        c = e[e.era == era].hr.value_counts().reindex(range(24), fill_value=0)
        bx.bar(np.arange(24) + off, c / c.sum(), .4, color=col, label=f"{era} (n={int(c.sum())})", edgecolor="#fcfcfb", linewidth=1)
    bx.set_xticks(range(0, 24, 3))
    bx.set_xlabel("Event start hour (Central time)")
    bx.set_ylabel("Share of ≥ $1,000 events")
    bx.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, 0))
    bx.set_title("When ≥ $1,000 events start", loc="left", fontsize=11.5, fontweight="bold", color="#0b0b0b")
    bx.legend(frameon=False, fontsize=9)
    fig.text(.01, .01, "Source: ERCOT NP6-785-ER historical RTM hub prices, HB_HOUSTON, 2022–2025. "
             "Events = runs of 15-min intervals ≥ threshold separated by > 60 min.", fontsize=8, color="#52514e")
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(out / "ercot_houston_spike_audit_2022_2025.png", dpi=180, facecolor="#fcfcfb")


if __name__ == "__main__":
    main()
