"""Check an independently regenerated result set against published aggregates.

Reads the actual output files, never README statements. Run on a freshly
recomputed output directory; optional --reference compares annual metrics.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def verify(out: Path, reference: Path | None = None) -> list[str]:
    counts = pd.read_csv(out/'real_audit'/'annual_spike_counts.csv')
    battery = pd.read_csv(out/'battery'/'annual_battery_spreads.csv')
    assert counts[['year','threshold']].notna().all().all()
    assert not counts.duplicated(['year','threshold']).any()
    assert (counts.declustered_events >= 0).all()
    assert set(battery.market) == {'RT','DA'}
    assert (battery.days >= 1).all()
    assert (battery.chronological_usd_per_mw_year >= -1e-8).all()
    messages = [f'Verified {len(counts)} annual spike rows and {len(battery)} battery-year rows']
    if reference is not None:
        for filename, keys, values in [('real_audit/annual_spike_counts.csv',['year','threshold'],['declustered_events']),('battery/annual_battery_spreads.csv',['year','market'],['chronological_usd_per_mw_year'])]:
            actual=pd.read_csv(out/filename).set_index(keys).sort_index()
            expected=pd.read_csv(reference/filename).set_index(keys).sort_index()
            if not actual.index.equals(expected.index):
                raise AssertionError(f'Index mismatch in {filename}')
            for col in values:
                np.testing.assert_allclose(actual[col],expected[col],rtol=1e-6,atol=0.05,err_msg=filename+':'+col)
            messages.append(f'Regenerated numbers match reference for {filename}')
    return messages

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default='results')
    ap.add_argument('--reference',default=None)
    args=ap.parse_args()
    for line in verify(Path(args.out),Path(args.reference) if args.reference else None):print(line)
if __name__=='__main__':main()
