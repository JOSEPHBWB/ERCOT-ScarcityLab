# Forecasting scaffold (synthetic only)

A point-in-time spike / RT − DA tail forecasting pipeline. It has **not** been run on real ERCOT forecast vintages;
every number under `results/` is from generated data and only tests the plumbing.

What it enforces:
- `validate()` rejects any feature whose `*_available_at` timestamp is after `decision_time`, duplicate UTC delivery hours,
  and missing values (no silent imputation).
- One decision per operating day at 15:00 CPT of the previous day (post-DAM).
- Expanding-window, non-overlapping monthly test folds.
- Comparators: logistic regression, gradient boosting, an unfitted reserve heuristic, and DA-price ranking
  (the hurdle any real model must clear), with a costed intervention scenario against a random-selection control.

```bash
cd forecasting_scaffold
python -m pytest -q                       # 8 tests
python run_demo.py --out results/demo_v03 # synthetic signal-recovery demo
```

To use it for real, assemble the hourly table described in `run_real.py` from archived forecast vintages
(see `../docs/FEATURE_AVAILABILITY_MATRIX.csv`) and run `python run_real.py --input <table.csv>`.
