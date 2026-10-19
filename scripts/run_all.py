"""Rebuild ERCOT research outputs from imported/processed market data.

Default stage `prices` requires the two historical Houston Hub CSV files.
`all` additionally requires processed SCED, fuel-mix and load files. No
results are silently filled in from tracked outputs.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def execute(script: str, *args: str) -> None:
    cmd = [sys.executable, str(ROOT / 'scripts' / script), *map(str, args)]
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)

def run(proc: Path, out: Path, stage: str) -> None:
    for name in ('rt15_HB_HOUSTON.csv', 'da_HB_HOUSTON.csv'):
        if not (proc / name).is_file():
            raise FileNotFoundError(f'Missing required input: {proc/name}')
    execute('run_price_audit.py', '--proc', proc, '--out', out / 'real_audit')
    execute('analyze_battery_spreads.py', '--proc', proc, '--out', out / 'battery')
    if stage == 'all':
        missing = [x for x in ('fuelmix_hourly.csv', 'load_hourly.csv', 'adders_2022.csv', 'adders_2023.csv', 'adders_2024.csv', 'adders_2025.csv') if not (proc / x).is_file()]
        if missing:
            raise FileNotFoundError(f'For --stage all first import {missing}')
        execute('analyze_adders.py', '--proc', proc, '--out', out / 'adders')
        execute('analyze_netload.py', '--proc', proc, '--adders', out / 'adders', '--out', out / 'netload')
        execute('validate_storage_proxy.py', '--proc', proc, '--out', out / 'netload')

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--proc', default='data/processed')
    ap.add_argument('--out', default='results')
    ap.add_argument('--stage', choices=['prices','all'], default='prices')
    args=ap.parse_args()
    run(Path(args.proc).resolve(),Path(args.out).resolve(),args.stage)

if __name__ == '__main__':
    main()
