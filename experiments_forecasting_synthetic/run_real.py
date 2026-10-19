"""Real-data execution only after verified point-in-time vintage table is supplied.

No demo fallback. Fails closed when the source CSV does not include availability fields.
"""
import argparse
from pathlib import Path
import pandas as pd
from src.pipeline import validate,make_labels,rolling_forecast,score,alert_stats

def main():
    p=argparse.ArgumentParser(description='PIT validated ERCOT CSV forecast')
    p.add_argument('--input',required=True,help='Audited real hourly PIT CSV with documented provenance')
    p.add_argument('--out',default='results/real_forecast')
    p.add_argument('--threshold',type=float,default=1000)
    p.add_argument('--spread-threshold',type=float,default=None)
    p.add_argument('--train-months',type=int,default=12)
    p.add_argument('--test-months',type=int,default=3)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    d=make_labels(validate(pd.read_csv(a.input)),a.threshold,spread_threshold=a.spread_threshold)
    preds,errors=rolling_forecast(d,a.train_months,a.test_months)
    if preds.empty:raise RuntimeError(f'No usable OOS folds: {errors}')
    preds.to_csv(out/'oos_predictions.csv',index=False)
    score(preds).to_csv(out/'scores.csv',index=False)
    alert_stats(preds).to_csv(out/'alert_metrics.csv',index=False)
    (out/'CAVEATS.txt').write_text('HISTORICAL REAL PRICE/FEATURE PIPELINE. Check data lineage and actual publication timestamps; proxy is not exact ORDC/ASDC. DA-conditioned post-DAM forecasting is not a retroactive DAM trading strategy.\n')
    print(score(preds).to_string(index=False));print('Skipped folds',errors)
if __name__=='__main__':main()
