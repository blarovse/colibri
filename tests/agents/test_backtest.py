"""Tests for the walk-forward backtest harness."""

import io
import os
import random
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from monday.backtest import backtest, demo_series, format_report, main  # noqa: E402


class TestBacktest(unittest.TestCase):
    def test_trending_series_shows_edge(self):
        rng = random.Random(3)
        v, series = 100.0, []
        for _ in range(150):
            v *= 1.0 + rng.gauss(0.004, 0.003)  # strong drift
            series.append(round(v, 4))
        r = backtest(series)
        self.assertGreaterEqual(r['hit_rate'], 0.8)
        self.assertEqual(r['verdict'], 'edge: model beat both baselines on this data')
        self.assertLess(r['brier'], r['brier_coin_flip'])

    def test_metrics_structure(self):
        r = backtest(demo_series())
        for key in ('points', 'predictions', 'warmup', 'hit_rate', 'brier',
                    'brier_coin_flip', 'brier_momentum', 'verdict_mix',
                    'confident_share', 'calibration', 'verdict', 'note'):
            self.assertIn(key, r)
        self.assertGreater(r['predictions'], 100)
        mixes = r['verdict_mix']
        self.assertEqual(
            mixes['UP'] + mixes['DOWN'] + mixes['SIDEWAYS'], r['predictions'])

    def test_hit_rate_bounds(self):
        r = backtest(demo_series())
        self.assertGreaterEqual(r['hit_rate'], 0.0)
        self.assertLessEqual(r['hit_rate'], 1.0)
        # a coin-flip Brier is exact 0.25 by construction
        self.assertAlmostEqual(r['brier_coin_flip'], 0.25, places=6)

    def test_calibration_buckets_sum(self):
        r = backtest(demo_series())
        total = sum(c['n'] for c in r['calibration'])
        self.assertEqual(total, r['predictions'])
        for c in r['calibration']:
            self.assertGreaterEqual(c['hit_rate'], 0.0)
            self.assertLessEqual(c['hit_rate'], 1.0)

    def test_too_short_series_errors(self):
        self.assertIn('error', backtest([1, 2, 3, 4, 5]))

    def test_no_lookahead_lengths(self):
        series = demo_series(60, seed=11)
        r = backtest(series, warmup=12)
        # n-1-warmup scored calls at most
        self.assertLessEqual(r['predictions'], len(series) - 1 - 12)

    def test_demo_series_deterministic(self):
        self.assertEqual(demo_series(50, seed=1), demo_series(50, seed=1))
        self.assertNotEqual(demo_series(50, seed=1), demo_series(50, seed=2))

    def test_format_report_renders(self):
        text = format_report(backtest(demo_series(80)))
        self.assertIn('hit rate', text)
        self.assertIn('Brier', text)
        self.assertIn('walk-forward', text.lower())

    def test_cli_demo(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(['--demo'])
        self.assertEqual(code, 0)
        self.assertIn('BACKTEST', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
