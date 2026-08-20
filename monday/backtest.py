#!/usr/bin/env python3
"""
Backtest harness for Jarvis's prediction engine.

Walk-forward evaluation: for every point in a series, Jarvis predicts the
next move using ONLY the data available up to that point, then the
prediction is scored against what actually happened. No look-ahead, no
curve-fitting — this is the honest scoreboard for the direction model.

Metrics:
- hit_rate            : verdict (UP/DOWN) matched the sign of the next move
- confident_hit_rate  : same, on the subset where confidence >= threshold
- brier               : mean (P(up) - outcome)^2  (lower is better, 0.25 = coin flip)
- baselines           : always-up, momentum (sign of last return)
- forecast_mae        : |next-value forecast - actual| vs naive (last value)
- calibration         : accuracy bucketed by stated confidence

CLI:
    python -m monday.backtest prices.csv
    python -m monday.backtest --demo          # seeded random-walk demo
"""

from typing import Dict, Any, List, Optional
import argparse
import math
import re
import sys

from .agents.prediction_agent import PredictionAgent


def _try_float(text: str) -> Optional[float]:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def load_series_file(path: str) -> List[float]:
    """
    Extract a price series from a CSV/TXT file, date-safe.

    Handles: "date,close" CSVs (with or without header), bare single-column
    files, and multi-column rows (takes the LAST numeric field, which is the
    close in date-first exports). Dates like 2025-08-21 never become prices.
    """
    with open(path, 'r', encoding='utf-8') as fh:
        lines = [ln.strip() for ln in fh.read().splitlines() if ln.strip()]

    def numbers_in(line: str) -> List[float]:
        out = []
        for field in re.split(r'[,;\t ]+', line):
            v = _try_float(field)
            if v is not None:
                out.append(v)
        return out

    rows = lines
    header = None
    if rows and not numbers_in(rows[0]):
        header = [h.strip().lower() for h in re.split(r'[,;\t]+', rows[0])]
        rows = rows[1:]

    values: List[float] = []
    if header:
        keys = ('close', 'adj close', 'adj_close', 'close/last', 'price', 'last', 'value')
        idx = next((i for i, h in enumerate(header)
                    if h.strip('"\ ') in keys or any(k in h for k in keys)),
                   len(header) - 1)
        for row in rows:
            fields = re.split(r'[,;\t]+', row)
            v = _try_float(fields[idx].strip('"\ ')) if idx < len(fields) else None
            if v is not None:
                values.append(v)
    else:
        for row in rows:
            nums = numbers_in(row)
            if not nums:
                continue
            values.append(nums[-1] if len(nums) > 1 else nums[0])

    if len(values) < 20:
        raise SystemExit(
            f"Need at least 20 points for a meaningful backtest (got {len(values)})."
        )
    return values


def demo_series(n: int = 200, seed: int = 7) -> List[float]:
    """Seeded random walk with mild drift, so results are reproducible."""
    import random
    rng = random.Random(seed)
    value, series = 100.0, []
    for _ in range(n):
        value *= 1.0 + rng.gauss(0.0008, 0.012)
        series.append(round(value, 4))
    return series


def backtest(values: List[float], warmup: int = 12,
             confidence_threshold: float = 0.6,
             agent: Optional[PredictionAgent] = None) -> Dict[str, Any]:
    """
    Run a walk-forward backtest of the direction and forecast engines.

    Args:
        values: full price series (oldest first), >= warmup+2 points
        warmup: number of leading points used before scoring starts
        confidence_threshold: confidence at/above which a prediction counts
            as "confident"
        agent: PredictionAgent instance (default: fresh one)

    Returns:
        Report dictionary with hit rates, Brier scores, baselines,
        calibration buckets and forecast errors.
    """
    agent = agent or PredictionAgent()
    values = [float(v) for v in values]
    n = len(values)
    if n < warmup + 5:
        return {'error': f"Need at least {warmup + 5} points (got {n})."}

    hits = 0
    total = 0
    confident_hits = 0
    confident_total = 0
    brier_jarvis = 0.0
    brier_coin = 0.0
    brier_momentum = 0.0
    verdict_counts = {'UP': 0, 'DOWN': 0, 'SIDEWAYS': 0}
    forecast_abs_err = 0.0
    naive_abs_err = 0.0
    forecast_points = 0
    buckets = {  # confidence bucket -> [hits, total]
        '50-60%': [0, 0], '60-70%': [0, 0], '70-80%': [0, 0], '80%+': [0, 0],
    }

    for i in range(warmup, n - 1):
        window = values[:i + 1]
        ret = (values[i + 1] - values[i]) / values[i] if values[i] else 0.0
        outcome_up = 1 if ret > 0 else 0

        pred = agent.predict_direction(window)
        if 'error' in pred:
            continue

        total += 1
        verdict_counts[pred['verdict']] += 1

        correct = (pred['verdict'] == 'UP' and ret > 0) or \
                  (pred['verdict'] == 'DOWN' and ret < 0)
        if correct:
            hits += 1

        conf = pred['confidence']
        if conf >= confidence_threshold:
            confident_total += 1
            if correct:
                confident_hits += 1

        # Brier score on P(up): outcome is binary (up = 1)
        p_up = pred['probabilities']['up'] / max(
            pred['probabilities']['up'] + pred['probabilities']['down'], 1e-9)
        brier_jarvis += (p_up - outcome_up) ** 2
        brier_coin += (0.5 - outcome_up) ** 2
        last_ret = (values[i] - values[i - 1]) / values[i - 1] if values[i - 1] else 0.0
        brier_momentum += ((1.0 if last_ret > 0 else 0.0) - outcome_up) ** 2

        # calibration bucket by stated confidence
        pct = conf * 100
        key = ('50-60%' if pct < 60 else '60-70%' if pct < 70
               else '70-80%' if pct < 80 else '80%+')
        buckets[key][1] += 1
        if correct:
            buckets[key][0] += 1

        # next-value forecast vs naive (repeat last value)
        if i % 5 == 0:  # sample forecasts to keep runtime snappy
            fc = agent.forecast_series(window)
            if 'error' not in fc:
                forecast_points += 1
                forecast_abs_err += abs(fc['next_value'] - values[i + 1])
                naive_abs_err += abs(values[i] - values[i + 1])

    if total == 0:
        return {'error': 'No scored predictions (series too short).'}

    calibration = [
        {'bucket': k, 'hit_rate': round(h / t, 3) if t else None, 'n': t}
        for k, (h, t) in buckets.items() if t
    ]

    return {
        'kind': 'backtest',
        'points': n,
        'predictions': total,
        'warmup': warmup,
        'hit_rate': round(hits / total, 3),
        'confident_hit_rate': round(confident_hits / confident_total, 3)
        if confident_total else None,
        'confident_share': round(confident_total / total, 3),
        'brier': round(brier_jarvis / total, 4),
        'brier_coin_flip': round(brier_coin / total, 4),
        'brier_momentum': round(brier_momentum / total, 4),
        'verdict_mix': verdict_counts,
        'forecast_mae': round(forecast_abs_err / forecast_points, 4)
        if forecast_points else None,
        'naive_mae': round(naive_abs_err / forecast_points, 4)
        if forecast_points else None,
        'calibration': calibration,
        'verdict': _grade(hits / total, brier_jarvis / total),
        'note': 'Walk-forward, zero look-ahead. Past accuracy never guarantees '
                'future results.',
    }


def _grade(hit_rate: float, brier: float) -> str:
    """Plain-language summary of the result."""
    if brier < 0.20 and hit_rate >= 0.60:
        return 'edge: model beat both baselines on this data'
    if hit_rate >= 0.55:
        return 'weak edge: slightly better than a coin flip'
    if abs(hit_rate - 0.5) < 0.05:
        return 'no measurable edge on this data'
    return 'model underperformed on this data — do not trust it here'


REPORT_TMPL = """
◆ BACKTEST — Jarvis direction model, walk-forward (no look-ahead)
  points: {points} · predictions: {predictions} · warmup: {warmup}

  hit rate          {hit_rate:.1%}
  confident (≥{thr:.0%})   {conf:>8}  ({share:.0%} of calls)
  baselines         coin-flip Brier {brier_coin:.3f} · momentum {brier_mom:.3f}
  Brier score       {brier:.3f}  (lower is better; 0.250 = coin flip)

  verdict mix       UP {up} · DOWN {down} · SIDEWAYS {side}
{forecast_line}
{calibration}
  ◆ {verdict}
  ◆ {note}
"""


def format_report(r: Dict[str, Any], confidence_threshold: float = 0.6) -> str:
    """Render a backtest report as console text."""
    if 'error' in r:
        return f"◆ {r['error']}"
    fc = ''
    if r['forecast_mae'] is not None:
        fc = (f"\n  forecast MAE      {r['forecast_mae']:g} "
              f"(naive {r['naive_mae']:g})")
    cal = ''
    if r['calibration']:
        rows = '  '.join(
            f"{c['bucket']}: {c['hit_rate']:.0%} (n={c['n']})"
            for c in r['calibration']
        )
        cal = f"\n  calibration       {rows}"
    return REPORT_TMPL.format(
        points=r['points'], predictions=r['predictions'], warmup=r['warmup'],
        hit_rate=r['hit_rate'],
        conf=f"{r['confident_hit_rate']:.1%}" if r['confident_hit_rate'] is not None else 'n/a',
        thr=confidence_threshold, share=r['confident_share'],
        brier=r['brier'], brier_coin=r['brier_coin_flip'],
        brier_mom=r['brier_momentum'],
        up=r['verdict_mix']['UP'], down=r['verdict_mix']['DOWN'],
        side=r['verdict_mix']['SIDEWAYS'],
        forecast_line=fc, calibration=cal,
        verdict=r['verdict'], note=r['note'],
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='monday.backtest',
        description="Walk-forward backtest of Jarvis's prediction engine.",
    )
    parser.add_argument('file', nargs='?', help='CSV/TXT file with a price series')
    parser.add_argument('--demo', action='store_true',
                        help='run on a seeded random-walk demo series')
    parser.add_argument('--warmup', type=int, default=12)
    parser.add_argument('--threshold', type=float, default=0.6,
                        help='confidence threshold for "confident" predictions')
    args = parser.parse_args(argv)

    if args.demo or not args.file:
        if not args.demo:
            print("no file given — using the seeded demo (or pass --demo to silence this)\n")
        series = demo_series()
        print(f"◆ demo series: {len(series)} points (seeded random walk, mild drift)")
    else:
        series = load_series_file(args.file)
        print(f"◆ loaded {len(series)} points from {args.file}")

    report = backtest(series, warmup=args.warmup,
                      confidence_threshold=args.threshold)
    print(format_report(report, args.threshold))
    return 0


if __name__ == '__main__':
    sys.exit(main())
