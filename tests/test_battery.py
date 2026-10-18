import numpy as np
import pandas as pd
from scripts.analyze_battery_spreads import dispatch_value, daily_values


def test_flat_prices_with_losses_cannot_make_money():
    assert dispatch_value(np.full(24, 50.0)) == 0


def test_negative_prices_create_correct_charge_incentive():
    p = np.full(24, 0.0)
    p[0] = -100
    assert dispatch_value(p) > 0


def test_order_matters():
    # A high price *before* the only negative charging opportunity
    # cannot be monetized with a zero initial SOC.
    p = np.zeros(24)
    p[0] = 200
    p[23] = -10
    assert dispatch_value(p) < 25


def test_summer_winter_and_daylength():
    idx = pd.date_range('2024-11-03 05:00:00+00:00', periods=25, freq='h', tz='UTC')
    # Local date includes 2024-11-03 00:00 through 23:00 with repeated 01:00.
    h = pd.DataFrame({'hour_utc':idx, 'price':np.arange(25, dtype=float)})
    h['day'] = h.hour_utc.dt.tz_convert('America/Chicago').dt.date
    d = daily_values(h)
    assert len(d) == 1 and d.hour_count.iloc[0] == 25
