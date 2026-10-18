"""Point-in-time-safe hourly DA-conditioned tail-risk research pipeline."""
import numpy as np
import pandas as pd
from scipy.stats import genpareto
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier

ZONE='America/Chicago'
FEATURES=['da_price','load_forecast','wind_forecast','solar_forecast','reserve_forecast','net_load_forecast','hour_sin','hour_cos','month_sin','month_cos']
CHANGE=pd.Timestamp('2025-12-05T00:00:00',tz=ZONE).tz_convert('UTC')

def validate(df, require_pit=True):
    z=df.copy()
    needed=['hour_utc','decision_time','da_price','rt_max','rt_mean']+FEATURES[1:]
    if require_pit: needed += ['da_available_at','load_available_at','wind_available_at','solar_available_at','reserve_available_at']
    missing=[x for x in needed if x not in z]
    if missing:raise ValueError('Missing required columns: '+', '.join(missing))
    for c in ['hour_utc','decision_time'] + (['da_available_at','load_available_at','wind_available_at','solar_available_at','reserve_available_at'] if require_pit else []):
        z[c]=pd.to_datetime(z[c],utc=True,errors='raise')
    if z['hour_utc'].duplicated().any(): raise ValueError('Duplicate UTC physical delivery hours')
    if require_pit:
        for c in ['da_available_at','load_available_at','wind_available_at','solar_available_at','reserve_available_at']:
            bad=z[c].isna()|(z[c]>z['decision_time'])
            if bad.any():raise ValueError(f'Look-ahead / unavailable vintage for {c}: {int(bad.sum())} rows')
        if (z['decision_time']>=z['hour_utc']).any():raise ValueError('Decision is not before delivery')
    if z[FEATURES+['rt_max','rt_mean']].isna().any().any():raise ValueError('Missing prices or features: no implicit imputation')
    if z['hour_utc'].dt.tz is None:raise ValueError('UTC timezone required')
    return z.sort_values('hour_utc').reset_index(drop=True)

def make_labels(df,threshold=1000,mode='max',spread_threshold=None):
    df=df.copy()
    value=df['rt_max'] if mode=='max' else df['rt_mean']
    if mode not in ['max','mean']:raise ValueError('mode must be max or mean')
    df['rt_spike']=(value>=threshold).astype(int)
    df['spread'] = df['rt_mean']-df['da_price']
    df['tail_label']=((df['spread']>spread_threshold) if spread_threshold is not None else (df['rt_spike']==1)).astype(int)
    return df

def demo_data(seed=42, days=365*3):
    """Entirely synthetic data. Never describe metrics as historical ERCOT evidence."""
    rng=np.random.default_rng(seed)
    h=pd.date_range('2023-01-01',periods=days*24,freq='h',tz='UTC')
    local=h.tz_convert(ZONE); hr=local.hour.to_numpy(); doy=local.dayofyear.to_numpy(); n=len(h)
    season=np.sin(2*np.pi*doy/365.25); wave=np.sin(2*np.pi*hr/24)
    load=51000+9500*season+7000*np.maximum(0,wave)+rng.normal(0,1800,n)
    wind=np.clip(9500-2000*season+rng.normal(0,2200,n),100,22000)
    solar=np.maximum(0,9500*np.sin(np.pi*np.maximum(0,(hr-6)/14)))+rng.normal(0,250,n)
    solar=np.clip(solar,0,None)
    reserve=np.clip(9300-0.16*(load-50000)+0.18*(wind-8000)+rng.normal(0,1400,n),200,18000)
    net=load-wind-solar
    pressure=np.maximum(0,(8200-reserve)/1700)
    da=np.clip(28+0.0012*(net-36000)+11*pressure+rng.normal(0,18,n),-60,650)
    post=(h>=CHANGE).astype(int)
    p=1/(1+np.exp(-(-5.2+1.65*pressure+0.018*np.maximum(da-65,0)-.8*post)))
    y=rng.random(n)<p
    spikes=y*(800+rng.pareto(2.8,n)*900)
    rt_mean=np.clip(da+rng.normal(0,26,n)+spikes,-180,4500)
    rt_max=np.clip(rt_mean+np.maximum(0,rng.normal(8,20,n)),rt_mean,5000)
    # One post-DAM decision at 15:00 America/Chicago on the PREVIOUS calendar day.
    delivery_day=local.normalize()
    decision_local=delivery_day-pd.Timedelta(days=1)+pd.Timedelta(hours=15)
    decision=decision_local.tz_convert('UTC')
    base=pd.DataFrame({'hour_utc':h,'decision_time':decision,'da_price':da,'rt_mean':rt_mean,'rt_max':rt_max,'load_forecast':load,'wind_forecast':wind,'solar_forecast':solar,'reserve_forecast':reserve,'net_load_forecast':net,'hour_sin':np.sin(2*np.pi*hr/24),'hour_cos':np.cos(2*np.pi*hr/24),'month_sin':np.sin(2*np.pi*local.month.to_numpy()/12),'month_cos':np.cos(2*np.pi*local.month.to_numpy()/12)})
    for k in ['da','load','wind','solar','reserve']:base[k+'_available_at']=decision-pd.Timedelta(minutes=30)
    return base

def monthly_splits(df,min_train_months=12,holdout_months=3):
    months=df.hour_utc.dt.tz_convert(ZONE).dt.tz_localize(None).dt.to_period('M')
    uniq=months.unique()
    for k in range(min_train_months,len(uniq),holdout_months):
        train=(months<uniq[k]).to_numpy(); test=((months>=uniq[k])&(months<uniq[min(k+holdout_months,len(uniq)-1)] + 1)).to_numpy() if k+holdout_months>=len(uniq) else ((months>=uniq[k])&(months<uniq[k+holdout_months])).to_numpy()
        # Guard on timestamps as well as calendar masks: no future train observation relative to test decisions.
        first_decision=df.loc[test,'decision_time'].min()
        train = train & (df.hour_utc < first_decision).to_numpy()
        if train.sum() and test.sum(): yield train,test,str(uniq[k])

def fit_models(train,test):
    xtrain=train[FEATURES].to_numpy(); xtest=test[FEATURES].to_numpy(); y=train.tail_label.to_numpy()
    if np.unique(y).size<2: raise ValueError('Training set has only one target class; collect more events or lower threshold')
    logit=make_pipeline(StandardScaler(),LogisticRegression(max_iter=800,class_weight=None))
    boost=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=12,l2_regularization=5,learning_rate=.06,min_samples_leaf=60,random_state=7)
    logit.fit(xtrain,y); boost.fit(xtrain,y)
    # Physical scarcity proxy, NOT an ERCOT protocol-equivalent ORDC/ASDC calculation.
    def proxy(s):
        reserve=s.reserve_forecast.to_numpy()
        da=s.da_price.to_numpy()
        return np.clip(1/(1+np.exp(-(-3.8+1.2*(4000-reserve)/1000+0.008*np.maximum(da-60,0)))),1e-5,1-1e-5)
    # Admissible post-DAM comparator: empirical DA-price ranking within each delivery day.
    # Scores are ranks, not calibrated probabilities; use for alert recall only.
    da_rank = test.groupby(test.hour_utc.dt.tz_convert(ZONE).dt.date)['da_price'].rank(pct=True)
    return {'logit':logit.predict_proba(xtest)[:,1],
            'boost':boost.predict_proba(xtest)[:,1],
            'scarcity_proxy_unfitted':proxy(test),
            'da_price_rank':da_rank.to_numpy()}

def rolling_forecast(df,train_months=12,test_months=3):
    out=[]; errors=[]
    for ti,te,period in monthly_splits(df,train_months,test_months):
        tr=df.loc[ti]; hold=df.loc[te]
        try: predictions=fit_models(tr,hold)
        except ValueError as e:errors.append({'period':period,'issue':str(e)});continue
        for model,p in predictions.items():
            block=hold[['hour_utc','decision_time','da_price','rt_mean','rt_max','spread','tail_label']].copy()
            block['model']=model;block['probability']=p;block['test_period']=period;out.append(block)
    return (pd.concat(out,ignore_index=True) if out else pd.DataFrame()),errors

def score(pred):
    rows=[]
    for name,d in pred.groupby('model'):
        if name == 'da_price_rank': continue  # ranking comparator, not probability forecast
        y=d.tail_label.to_numpy(); p=np.clip(d.probability.to_numpy(),1e-8,1-1e-8)
        rows.append({'model':name,'n':len(y),'positives':int(y.sum()),'base_rate':float(y.mean()),'pr_auc':float(average_precision_score(y,p)) if y.sum()>0 else np.nan,'brier':float(brier_score_loss(y,p)),'log_loss':float(log_loss(y,p,labels=[0,1])),'roc_auc':float(roc_auc_score(y,p)) if len(np.unique(y))==2 else np.nan})
    return pd.DataFrame(rows).sort_values('brier')

def tail_gpd(df,u=100,minimum=25):
    """Fit a bounded, fixed-param explanatory GPD on spread exceedances (not predictive)."""
    x=df.loc[df.spread>u,'spread'].to_numpy()-u
    if len(x)<minimum:return {'status':'insufficient','exceedances':int(len(x)),'minimum':minimum}
    xi,_,scale=genpareto.fit(x,floc=0)
    return {'status':'fitted_in_sample_diagnostic','exceedances':len(x),'threshold':u,'xi':float(xi),'scale':float(scale),'note':'In-sample diagnostic ONLY; no OOS claim and no cap-truncated likelihood.'}

def alert_stats(df,budget_per_day=3):
    rows=[]
    for name,d in df.groupby('model'):
        d=d.copy();d['day']=d.hour_utc.dt.tz_convert(ZONE).dt.date
        # Alert budget is applied to candidate delivery hours each local operating day.
        d['rank']=d.groupby('day').probability.rank(method='first',ascending=False)
        alert=d['rank']<=budget_per_day
        captured=int(d.loc[alert,'tail_label'].sum()); total=int(d.tail_label.sum())
        rows.append({'model':name,'alert_hours':int(alert.sum()),'captured_spikes':captured,'total_spikes':total,'event_recall':captured/total if total else np.nan,'precision_at_budget':captured/alert.sum() if alert.sum() else np.nan})
    return pd.DataFrame(rows)

def exposure_backtest(pred,notional_mw=1.,risk_penalty=0.):
    """Hypothetical PRE-EXISTING short RT-DA spread exposure; hedging signal is illustrative, not executable DAM trade."""
    z=pred.copy(); # Daily highest-risk hours selected under a limited operational risk budget.
    z['delivery_day'] = z.hour_utc.dt.tz_convert(ZONE).dt.date
    z['hedge'] = z.groupby('delivery_day')['probability'].rank(
        method='first', ascending=False
    ) <= 3
    z['unhedged_pnl']=-notional_mw*z.spread
    z['hypothetical_hedge_effect']=np.where(z.hedge,notional_mw*z.spread,0.)
    z['hedged_pnl']=z.unhedged_pnl+z.hypothetical_hedge_effect
    z['loss_unhedged']=-z.unhedged_pnl
    return z

def expected_shortfall(loss,alpha=.95):
    x=np.asarray(loss); q=np.quantile(x,alpha);return float(np.mean(x[x>=q]))


def compare_operational_risk(pred, budget_per_day=3, intervention_cost=35.0, effectiveness=0.75, seed=71):
    """Compare model, DA ranking and fixed-seed random daily interventions.

    Pre-existing exposure has loss RT_mean - DA. Intervention mitigates only
    positive spread loss, by assumed effectiveness; incurs cost for every
    protected MW-hour. This is a scenario, not a replicable ERCOT trade.
    """
    if not 0 <= effectiveness <= 1 or intervention_cost < 0:
        raise ValueError('Invalid intervention assumptions')
    from numpy.random import default_rng
    rng = default_rng(seed)
    d = pred.copy().sort_values('hour_utc')
    d['day'] = d.hour_utc.dt.tz_convert(ZONE).dt.date
    choices = {}
    for name, g in d.groupby('model'):
        g = g.copy()
        ranks = g.groupby('day').probability.rank(method='first', ascending=False)
        g['selected'] = ranks <= budget_per_day
        choices[name] = g
        if name == 'logit':
            random_g = g.copy()
            random_g['model'] = 'random_daily_3'
            random_g['selected'] = False
            for _, group in random_g.groupby('day'):
                idx = rng.choice(group.index.to_numpy(), size=min(budget_per_day,len(group)),replace=False)
                random_g.loc[idx,'selected'] = True
            choices['random_daily_3'] = random_g
    rows = []
    for name,g in choices.items():
        original = g.spread.to_numpy()
        selected = g.selected.to_numpy()
        cost = selected * intervention_cost
        mitigated = selected * effectiveness * np.maximum(original,0.)
        net_loss = original - mitigated + cost
        rows.append({'model':name,'selected_hours':int(selected.sum()),
                     'spike_recall':float(g.loc[g.selected,'tail_label'].sum()/max(1,g.tail_label.sum())),
                     'ES95_unmitigated':expected_shortfall(original),
                     'ES95_after_cost':expected_shortfall(net_loss),
                     'mean_cost_per_hour':float(cost.mean()),
                     'mean_net_loss':float(net_loss.mean())})
    return pd.DataFrame(rows)
