"""A small offline full-pipeline test with constructed hourly/15m prices."""
import pandas as pd
import numpy as np
from scripts.analyze_battery_spreads import load_hourly, daily_values
from week1_audit import audit


def test_one_day_prices_through_audit_and_dispatch(tmp_path):
    # A complete winter operating day, UTC starts for America/Chicago.
    hours = pd.date_range('2025-01-10 06:00:00+00:00', periods=24, freq='h')
    da = pd.DataFrame({'start': hours, 'end': hours + pd.Timedelta(hours=1), 'price': [20.] * 24})
    quarters = pd.date_range(hours[0], periods=96, freq='15min')
    prices = np.full(96, 20.0)
    prices[72:76] = 1500.0
    rt = pd.DataFrame({'start':quarters,'end':quarters + pd.Timedelta(minutes=15),'price':prices})
    hourly, counts, events, quality = audit(rt,da,None)
    assert len(hourly) == 24
    assert (quality == 4).all()
    assert int(counts.query('year == 2025 and threshold == 1000').declustered_events.iloc[0]) == 1
    file = tmp_path/'rt.csv'
    rt.to_csv(file,index=False)
    result = daily_values(load_hourly(file))
    assert len(result) == 1
    assert result.iloc[0].chronological_usd_per_mw_day > 0
