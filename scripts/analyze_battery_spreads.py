"""ERCOT Houston Hub battery energy-only opportunity audit.

TB2 is an ex-post price spread, NOT revenue. Chronological dispatch has
1 MW power, 2 MWh usable SOC, 85% round-trip efficiency, zero initial and
terminal daily SOC, no ancillary services, price impact, fees or degradation.
Discretized SOC grid (0.125 MWh) prevents simultaneous charge/discharge.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ZONE = 'America/Chicago'
ETA = np.sqrt(0.85)


def load_hourly(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, usecols=['start', 'price'])
    d['start'] = pd.to_datetime(d['start'], utc=True)
    if d.start.duplicated().any():
        raise ValueError(f'Duplicate timestamps: {path}')
    h = d.assign(hour_utc=d.start.dt.floor('h')).groupby('hour_utc', as_index=False).price.mean()
    h['day'] = h.hour_utc.dt.tz_convert(ZONE).dt.date
    h['year'] = pd.to_datetime(h.day).dt.year
    return h


def dispatch_value(prices: np.ndarray, capacity=2.0, power=1.0, soc_step=0.125) -> float:
    """Hourly SOC-grid dynamic program; 0 SOC start/end, $ for a 1 MW battery.

    Move SOC by delta: positive => buy delta/eta_charge from market;
    negative => sell (-delta)*eta_discharge to market.
    """
    p = np.asarray(prices, dtype=float)
    if not len(p) or not np.isfinite(p).all():
        raise ValueError('Prices must be nonempty and finite')
    states = np.linspace(0, capacity, round(capacity / soc_step) + 1)
    delta = states[None, :] - states[:, None]  # from rows, to columns
    feasible = (delta <= power * ETA + 1e-10) & (-delta <= power / ETA + 1e-10)
    volume = np.where(delta >= 0, -delta / ETA, -delta * ETA)
    dp = np.full(len(states), -np.inf)
    dp[0] = 0.0
    for price in p:
        revenue = np.where(feasible, price * volume, -np.inf)
        dp = (dp[:, None] + revenue).max(axis=0)
    return float(max(dp[0], 0.0))


def daily_values(h: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for day, part in h.sort_values('hour_utc').groupby('day'):
        p = part.price.to_numpy(dtype=float)
        # DST days may have 23 or 25 hours, both are legitimate.
        if len(p) not in (23, 24, 25):
            raise ValueError(f'Incomplete local day {day}: {len(p)} hourly observations')
        s = np.sort(p)
        rows.append({
            'day': str(day), 'year': day.year, 'hour_count': len(p),
            'tb2_spread_usd_per_mwh': float(s[-2:].mean() - s[:2].mean()),
            'tb4_spread_usd_per_mwh': float(s[-4:].mean() - s[:4].mean()),
            'max_price': float(s[-1]),
            'gross_tb2_expost_usd_per_mw_day': float(s[-2:].sum() - s[:2].sum()),
            'chronological_usd_per_mw_day': dispatch_value(p),
        })
    return pd.DataFrame(rows)


def summarize(d: pd.DataFrame, market: str) -> pd.DataFrame:
    rows = []
    for year, g in d.groupby('year'):
        annual = g.chronological_usd_per_mw_day.sum()
        top = g.chronological_usd_per_mw_day.nlargest(10).sum()
        rows.append({
            'market': market, 'year': year, 'days': len(g),
            'tb2_spread_mean_usd_per_mwh': g.tb2_spread_usd_per_mwh.mean(),
            'tb2_spread_median_usd_per_mwh': g.tb2_spread_usd_per_mwh.median(),
            'gross_tb2_expost_usd_per_mw_year': g.gross_tb2_expost_usd_per_mw_day.sum(),
            'chronological_usd_per_mw_year': annual,
            'top10_day_share': top / annual if annual > 0 else np.nan,
            'spike_day_share': (g.loc[g.max_price >= 1000, 'chronological_usd_per_mw_day'].sum() / annual if annual > 0 else np.nan),
            'spike_days': int((g.max_price >= 1000).sum()),
        })
    return pd.DataFrame(rows)


def analyze(rt: pd.DataFrame, da: pd.DataFrame, out: Path) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    rt_daily, da_daily = daily_values(rt), daily_values(da)
    rt_daily.to_csv(out / 'daily_spreads_rt.csv', index=False)
    da_daily.to_csv(out / 'daily_spreads_da.csv', index=False)
    summary = pd.concat([summarize(rt_daily, 'RT'), summarize(da_daily, 'DA')], ignore_index=True)
    summary.to_csv(out / 'annual_battery_spreads.csv', index=False)
    years = sorted(summary.year.unique())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for idx, market in enumerate(('RT', 'DA')):
        subset = summary[summary.market == market].set_index('year').reindex(years)
        axes[0].bar(np.arange(len(years)) + (idx-.5)*.38, subset.chronological_usd_per_mw_year/1000,
                    .36, label=market)
    axes[0].set_xticks(range(len(years)), years)
    axes[0].set_ylabel('Chronological energy opportunity ($k / MW-year)')
    axes[0].set_title('1 MW / 2 MWh; 85% round-trip efficiency')
    axes[0].legend(frameon=False)
    subset = summary[summary.market == 'RT'].set_index('year').reindex(years)
    axes[1].bar([str(y) for y in years], 100*subset.top10_day_share)
    axes[1].set_ylabel('Share of annual chronological value (%)')
    axes[1].set_title('Concentration in 10 highest-value days')
    fig.suptitle('ERCOT Houston: energy-only battery opportunity, 2022–2025', fontsize=13)
    fig.tight_layout()
    fig.savefig(out / 'ercot_battery_arbitrage_2022_2025.png', dpi=180)
    plt.close(fig)
    (out / 'battery_report.txt').write_text(
        'EX-POST OPPORTUNITY, NOT ACHIEVED TRADING REVENUE.\n'
        '1 MW / 2 MWh; 85% round-trip efficiency; 0.125 MWh SOC grid; '
        'daily SOC reset; hourly average RT / hourly DA; no trading fees, '
        'degradation, ancillary services, or price impact.\n\n' +
        summary.round(3).to_string(index=False) + '\n')
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--proc', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    proc = Path(args.proc)
    analyze(load_hourly(proc / 'rt15_HB_HOUSTON.csv'),
            load_hourly(proc / 'da_HB_HOUSTON.csv'), Path(args.out))


if __name__ == '__main__':
    main()
