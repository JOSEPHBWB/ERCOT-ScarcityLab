import numpy as np
import pandas as pd
from scripts.validate_storage_proxy import validate


def test_battery_like_series_is_recognised():
    idx = pd.date_range("2025-01-01 06:00", periods=24 * 400, freq="h", tz="UTC")
    hour = idx.tz_convert("America/Chicago").hour
    scale = np.random.default_rng(0).uniform(0.5, 1.5, len(idx) // 24).repeat(24)
    charge = np.where((hour >= 9) & (hour <= 12), 100.0, 0.0) * scale
    other = np.where((hour >= 18) & (hour <= 21), 85.0, 0.0) * scale
    f = pd.DataFrame({"hour_utc": idx.astype(str), "Other": other, "WSL": -charge})
    annual, profile, corr = validate(f)
    assert np.allclose(annual.discharge_over_charge, 0.85, atol=0.01)
    assert profile.loc[19, "Other"] > profile.loc[10, "Other"]
    assert profile.loc[10, "charge"] > profile.loc[19, "charge"]
    assert corr > 0.95
