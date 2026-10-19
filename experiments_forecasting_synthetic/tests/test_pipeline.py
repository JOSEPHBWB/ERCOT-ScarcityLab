import pytest
import pandas as pd
from src.pipeline import demo_data,validate,make_labels,monthly_splits,tail_gpd

def test_vintage_rejection():
    x=demo_data(days=5);x.loc[0,'wind_available_at']=x.loc[0,'decision_time']+pd.Timedelta(minutes=1)
    with pytest.raises(ValueError,match='Look-ahead'):validate(x)

def test_utc_hour_uniqueness():
    x=demo_data(days=3)
    x.loc[1,'hour_utc']=x.loc[0,'hour_utc']
    with pytest.raises(ValueError,match='Duplicate'):validate(x)

def test_splits_have_no_future_training_labels():
    x=make_labels(validate(demo_data(days=365*2)))
    for tr,te,_ in monthly_splits(x):
        assert x.loc[tr,'hour_utc'].max()<x.loc[te,'decision_time'].min()

def test_gpd_guard():
    x=make_labels(validate(demo_data(days=3)))
    assert tail_gpd(x,u=999999)['status']=='insufficient'


def test_synthetic_known_signal_is_recovered():
    """This tests code plumbing, NOT ERCOT predictive skill."""
    from sklearn.metrics import roc_auc_score
    from src.pipeline import fit_models
    df = make_labels(validate(demo_data(days=500)))
    train = df.iloc[:365 * 24]
    test = df.iloc[365 * 24:]
    pred = fit_models(train, test)['logit']
    assert roc_auc_score(test.tail_label, pred) > 0.65


def test_one_local_decision_per_delivery_day():
    df = demo_data(days=20)
    local_delivery = df.hour_utc.dt.tz_convert('America/Chicago').dt.date
    counts = df.groupby(local_delivery)['decision_time'].nunique()
    assert (counts == 1).all()


def test_da_rank_matches_da_price_order():
    from src.pipeline import fit_models
    d=make_labels(validate(demo_data(days=500)))
    tr=d.iloc[:365*24]; te=d.iloc[365*24:]
    actual=fit_models(tr,te)['da_price_rank']
    expected=te.groupby(te.hour_utc.dt.tz_convert('America/Chicago').dt.date).da_price.rank(pct=True)
    assert (abs(actual-expected.to_numpy()) < 1e-12).all()

def test_costed_risk_has_random_control():
    from src.pipeline import rolling_forecast,compare_operational_risk
    d=make_labels(validate(demo_data(days=500)))
    preds,_=rolling_forecast(d)
    a=compare_operational_risk(preds)
    assert {'random_daily_3','da_price_rank','logit'} <= set(a.model)
    assert a.mean_cost_per_hour.gt(0).all()
