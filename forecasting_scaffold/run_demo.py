"""Fully reproducible synthetic demonstration; never ERCOT observed evidence."""
import argparse,json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.pipeline import demo_data,validate,make_labels,rolling_forecast,score,alert_stats,tail_gpd,exposure_backtest,expected_shortfall,compare_operational_risk,CHANGE

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='results/demo');p.add_argument('--days',type=int,default=365*3);p.add_argument('--threshold',type=float,default=1000);a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    d=make_labels(validate(demo_data(days=a.days)),a.threshold)
    d['year']=d.hour_utc.dt.tz_convert('America/Chicago').dt.year
    count=d.groupby('year').agg(hours=('tail_label','size'),spike_hours=('tail_label','sum')).reset_index()
    count.to_csv(out/'synthetic_annual_counts.csv',index=False)
    preds,errors=rolling_forecast(d); 
    if preds.empty:raise RuntimeError('No eligible OOS prediction folds: '+str(errors))
    preds.to_csv(out/'synthetic_oos_predictions.csv',index=False)
    sc=score(preds);sc.to_csv(out/'synthetic_oos_scores.csv',index=False)
    alert=alert_stats(preds);alert.to_csv(out/'synthetic_alert_metrics.csv',index=False)
    gpd=tail_gpd(d);(out/'synthetic_tail_fit.json').write_text(json.dumps(gpd,indent=2))
    operational=compare_operational_risk(preds)
    operational.to_csv(out/'synthetic_costed_risk.csv',index=False)
    fig,ax=plt.subplots(figsize=(10,5));piv=preds.groupby(['model',pd.cut(preds.probability,bins=[0,.01,.03,.06,.1,.2,.4,.6,1],include_lowest=True)],observed=True).agg(pred=('probability','mean'),actual=('tail_label','mean')).reset_index()
    for model,t in piv.groupby('model'):ax.plot(t.pred,t.actual,marker='o',label=model)
    ax.plot([0,1],[0,1],linestyle='--',color='gray');ax.set(xlabel='Mean predicted probability',ylabel='Observed event fraction',title='SYNTHETIC DEMO: out-of-sample reliability');ax.legend();fig.tight_layout();fig.savefig(out/'synthetic_reliability.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4));ax.bar(count.year.astype(str),count.spike_hours);ax.set(xlabel='Synthetic year',ylabel='Synthetic labeled hours',title='SYNTHETIC DEMO — NOT ERCOT HISTORICAL DATA');fig.tight_layout();fig.savefig(out/'synthetic_annual_spikes.png',dpi=160);plt.close(fig)
    report=f'''# SYNTHETIC demonstration — NOT historical ERCOT results\n\nLabel: hourly `max(RT 15-min)>={a.threshold}` approximated by synthetic rt_max. Decision: post-DAM, before delivery. No executable trade is claimed.\n\n## Out-of-sample scores\n\n{sc.to_markdown(index=False)}\n\n## Fixed daily alert budget\n\n{alert.to_markdown(index=False)}\n\n## Costed intervention comparison (USD per protected MW-hour, synthetic)\n\n{operational.to_markdown(index=False)}\n\n## Scope\n- All prices, features, publication times and labels are **generated**. Do not cite as empirical findings.\n- `scarcity_proxy_unfitted` is an illustrative reserve-based benchmark, NOT an exact ORDC/ASDC reproduction.\n- GPD fit is an **in-sample diagnostic**, not an out-of-sample predictive EVT model.\n- Operational intervention assumes $35/MW-hour and 75% effectiveness; compares daily DA ranking and random selection. No executable product is implied.\n- Pre/post change has neither controlled attribution nor enough synthetic post-change evidence to justify a real claim.\n- RTC+B boundary is {CHANGE}; synthetic samples alone cannot identify its impact.\n- Skipped folds: {errors}\n'''
    (out/'REPORT.md').write_text(report)
    print(report)
if __name__=='__main__':main()
