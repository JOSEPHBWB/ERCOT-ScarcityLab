"""ERCOT ScarcityLab: Week 1 price-only spike audit.

This script is an exploratory historical-label audit, NOT a point-in-time
backtest. No forecast vintages or DAM availability assumptions are inferred.

Usage:
 python week1_audit.py --start 2024-07-01 --end 2024-07-08
 python week1_audit.py --start 2022-01-01 --end 2026-10-01 --sleep 0.2

Dates are ERCOT-local operating dates; --end is EXCLUSIVE.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ZONE = 'America/Chicago'
HUB = 'HB_HOUSTON'
THRESHOLDS = (500, 1000, 2000, 4500, 5000)


def fetch_one(iso, date, market, cache):
    path = cache / f'{date:%Y%m%d}_{market}.csv'
    if path.exists():
        data = pd.read_csv(path)
    else:
        raw = iso.get_spp(date=pd.Timestamp(date), market=market,
                          location_type='Trading Hub')
        data = raw.loc[raw['Location'].eq(HUB),
                       ['Interval Start','Interval End','SPP']].copy()
        if data.empty:
            raise ValueError(f'{date} {market}: {HUB} not present')
        data.to_csv(path, index=False)
    data['start'] = pd.to_datetime(data['Interval Start'], utc=True)
    data['end'] = pd.to_datetime(data['Interval End'], utc=True)
    data['price'] = pd.to_numeric(data['SPP'], errors='raise')
    assert data['start'].notna().all() and data['price'].notna().all()
    return data[['start','end','price']].drop_duplicates('start').sort_values('start')


def retrieve(iso, dates, market, cache, sleep):
    pieces, failures = [], []
    for i, date in enumerate(dates, 1):
        try:
            pieces.append(fetch_one(iso, date, market, cache))
        except Exception as exc:
            failures.append({'date':str(date.date()),'market':market,'error':str(exc)})
        if len(failures) >= 5 and not pieces:
            raise RuntimeError(f'{market}: first five days all failed; stopping early. Errors: {failures[:2]}')
        if i % 30 == 0:
            print(market, 'days attempted', i, '/', len(dates), 'failed', len(failures))
        if sleep: time.sleep(sleep)
    if not pieces:
        raise RuntimeError(f'No {market} data fetched. First errors: {failures[:3]}')
    return pd.concat(pieces, ignore_index=True).drop_duplicates('start').sort_values('start'), failures


def audit(rt, da, end):
    # Hour bins are defined in UTC to preserve both autumn DST repeated hours.
    rt = rt.copy()
    rt['hour_utc'] = rt['start'].dt.floor('h')
    rt['year'] = rt['start'].dt.tz_convert(ZONE).dt.year
    da = da.rename(columns={'price':'da_price', 'start':'hour_utc'})
    # Strict cardinality: one DA settlement point price per physical hour.
    if da['hour_utc'].duplicated().any():
        raise ValueError('Duplicate DA UTC hours: inspect DST/source before joining')
    qcounts = rt.groupby('hour_utc').size()
    hourly = rt.groupby('hour_utc',as_index=False).agg(
        rt_max=('price','max'), rt_mean=('price','mean'),
        n_rt_intervals=('price','size'))
    hourly = hourly.merge(da[['hour_utc','da_price']], on='hour_utc', how='left',
                          validate='one_to_one')
    hourly['year'] = hourly['hour_utc'].dt.tz_convert(ZONE).dt.year
    hourly['rt_da_spread_mean'] = hourly['rt_mean'] - hourly['da_price']
    hourly['rt_da_spread_max'] = hourly['rt_max'] - hourly['da_price']
    out = []
    events = []
    for u in THRESHOLDS:
        flagged = rt[rt['price'] >= u].sort_values('start').copy()
        # A gap > 60 minutes between consecutive exceedance intervals starts a new event.
        # The interval may contain <=threshold periods within a cluster.
        if not flagged.empty:
            flagged['event_id'] = flagged['start'].diff().gt(pd.Timedelta('60min')).cumsum()
            ev = flagged.groupby('event_id', as_index=False).agg(
                first_interval=('start','min'),last_interval=('end','max'),
                peak=('price','max'), exceedance_intervals=('price','size'))
            ev['threshold'] = u
            ev['year'] = ev['first_interval'].dt.tz_convert(ZONE).dt.year
            events.append(ev)
        g = rt.assign(hit=rt['price'] >= u).groupby('year')['hit'].agg(['sum','count'])
        hs = hourly.assign(any_hit=hourly['rt_max'] >= u,
                           mean_hit=hourly['rt_mean'] >= u)
        h = hs.groupby('year')[['any_hit','mean_hit']].sum()
        n = (ev.groupby('year').size() if not flagged.empty else pd.Series(dtype='int64'))
        for year in sorted(g.index):
            out.append({'year':year, 'threshold':u,
                        'rt15_exceedances':int(g.loc[year,'sum']),
                        'observed_rt15':int(g.loc[year,'count']),
                        'any_15m_hour_hits':int(h.loc[year,'any_hit']),
                        'hour_mean_hits':int(h.loc[year,'mean_hit']),
                        'declustered_events':int(n.get(year,0))})
    ev_all = pd.concat(events, ignore_index=True) if events else pd.DataFrame()
    return hourly, pd.DataFrame(out), ev_all, qcounts


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--start', default='2024-07-01')
    ap.add_argument('--end',default='2024-07-08',help='Exclusive')
    ap.add_argument('--out',default='results')
    ap.add_argument('--sleep',type=float,default=0.1)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    cache=out/'cache'; cache.mkdir(exist_ok=True)
    start=pd.Timestamp(args.start); end=pd.Timestamp(args.end)
    if end <= start: raise ValueError('end must be later than start')
    dates=pd.date_range(start,end-pd.Timedelta(days=1),freq='D')
    try:
        from gridstatus import Ercot
    except ImportError as exc:
        raise SystemExit("Install gridstatus for online data fetching; offline audit needs no gridstatus") from exc
    iso=Ercot()
    rt,fail_rt=retrieve(iso,dates,'REAL_TIME_15_MIN',cache,args.sleep)
    da,fail_da=retrieve(iso,dates,'DAY_AHEAD_HOURLY',cache,args.sleep)
    hourly,counts,events,qcounts=audit(rt,da,end)
    rt.to_csv(out/'rt15_houston.csv',index=False)
    hourly.to_csv(out/'hourly_houston.csv',index=False)
    counts.to_csv(out/'annual_spike_counts.csv',index=False)
    events.to_csv(out/'declustered_events.csv',index=False)
    with open(out/'quality_report.json','w') as f:
        json.dump({'rt_failures':fail_rt,'da_failures':fail_da,
                   'rt_intervals':len(rt), 'da_hours_with_missing_match':int(hourly['da_price'].isna().sum()),
                   'non_four_interval_hours':int((qcounts != 4).sum()),
                   'near_4500_rt15_count':int((rt['price'] >= 4500).sum()),
                   'at_or_above_5000_rt15_count':int((rt['price'] >= 5000).sum()),
                   'maximum_rt_spp':float(rt['price'].max()),
                   'coverage_first':str(rt['start'].min()),'coverage_last':str(rt['end'].max()),
                   'note':'Offer caps are NOT a strict bound on Houston Hub settlement point price. Hourly bins UTC. Incomplete hours are NOT excluded from counts; inspect quality first.'},f,indent=2)
    wide=counts.pivot(index='year',columns='threshold',values='declustered_events')
    ax=wide.plot.bar(figsize=(9,5),rot=0)
    ax.set(title=f'ERCOT {HUB}: Declustered RT spike events (gap > 60 min)',
           xlabel='Operating year',ylabel='Independent clusters (observed)')
    ax.figure.tight_layout()
    ax.figure.savefig(out/'annual_spike_events.png',dpi=180)
    print('\n',counts.to_string(index=False))
    print('\nQuality report:',out/'quality_report.json')
    print('Reminder: compare complete matching calendar windows; 2026 is partial.')

if __name__=='__main__': main()
