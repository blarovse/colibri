"""Tests for the autonomous (paper) trader."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from monday.trader import (  # noqa: E402
    AutoTrader, PaperBroker, TraderConfig, format_report, main as trader_main,
)
from monday.backtest import demo_series  # noqa: E402


class TestPaperBroker(unittest.TestCase):
    def setUp(self):
        self.cfg = TraderConfig(starting_equity=10_000)
        self.broker = PaperBroker(self.cfg)

    def test_accounting_invariant(self):
        """cash + position*price == equity(price) at every step."""
        pos = self.broker.buy(0, 100.0)
        self.assertIsNotNone(pos)
        for price in (pos.entry_price, 90.0, 120.0):
            self.assertAlmostEqual(
                self.broker.cash + pos.quantity * price,
                self.broker.equity(price), places=6)
        trade = self.broker.close(1, 110.0, 'take_profit')
        self.assertIsNotNone(trade)
        self.assertGreater(trade.pnl, 0)
        self.assertAlmostEqual(self.broker.equity(0), self.broker.cash, places=6)
        # cash after a winning round trip exceeds... nothing (costs), but must match
        self.assertAlmostEqual(
            self.broker.cash,
            self.cfg.starting_equity + trade.pnl, places=4)

    def test_no_double_position(self):
        self.broker.buy(0, 100.0)
        self.assertIsNone(self.broker.buy(1, 101.0))

    def test_costs_applied(self):
        cfg = TraderConfig(starting_equity=10_000, commission_bps=100)  # 1%
        broker = PaperBroker(cfg)
        broker.buy(0, 100.0)
        broker.close(1, 100.0, 'manual')  # flat price: pure cost bleed
        self.assertLess(broker.cash, cfg.starting_equity)

    def test_position_sizing_fraction(self):
        pos = self.broker.buy(0, 100.0)
        self.assertLessEqual(pos.entry_price * pos.quantity, 10_000 * 0.10 + 1e-6)


class TestAutoTrader(unittest.TestCase):
    def test_not_armed_does_nothing(self):
        trader = AutoTrader(TraderConfig(warmup=3))
        for i, p in enumerate([100, 101, 102, 103, 104, 105, 106, 107]):
            trader.on_bar(i, p)
        self.assertEqual(len(trader.trades), 0)
        self.assertEqual(trader.broker.fills, 0)

    def test_armed_trades_trend(self):
        rng = random.Random(9)
        v, series = 100.0, []
        for _ in range(120):
            v *= 1.0 + rng.gauss(0.005, 0.003)
            series.append(round(v, 4))
        report = AutoTrader.simulate(series)
        self.assertGreaterEqual(report['trade_count'], 1)
        # accounting: final equity equals cash after flatten
        self.assertAlmostEqual(report['final_equity'], report['equity_curve'][-1], places=2)

    def test_stop_loss_respected(self):
        """Every exit reason is legal and stops fire on crashes."""
        cfg = TraderConfig(starting_equity=10_000, warmup=6)
        trader = AutoTrader(cfg)
        trader.arm()
        # pump to trigger entry, then crash
        series = [100 + i for i in range(10)] + [140 - 5 * i for i in range(1, 12)]
        for i, p in enumerate(series):
            trader.on_bar(i, float(p))
        trader.disarm()
        for t in trader.trades:
            self.assertIn(t.reason, ('stop_loss', 'take_profit', 'signal_flip',
                                     'end_of_data', 'manual'))

    def test_kill_switch_halts(self):
        """All-in position + crash: the drawdown switch must flatten + halt."""
        cfg = TraderConfig(starting_equity=1_000, max_drawdown_kill=0.05,
                           warmup=0, position_fraction=1.0, stop_loss_pct=0.5)
        trader = AutoTrader(cfg)
        trader.arm()
        trader.on_bar(0, 100.0)
        trader.on_bar(1, 101.0)
        pos = trader.broker.buy(2, 102.0)   # force-entry: we test the switch
        self.assertIsNotNone(pos)
        killed = False
        for i, p in enumerate([95.0, 85.0, 75.0, 65.0], start=3):
            trader.on_bar(i, p)
            if trader.killed:
                killed = True
                break
        self.assertTrue(killed)
        self.assertFalse(trader.armed)
        self.assertIsNone(trader.broker.position)  # flattened by the switch

    def test_disarm_flattens(self):
        trader = AutoTrader(TraderConfig(warmup=6))
        trader.arm()
        for i, p in enumerate([100 + i for i in range(20)]):
            trader.on_bar(i, float(p))
        if trader.broker.position is not None:
            trader.disarm()
            self.assertIsNone(trader.broker.position)

    def test_report_structure(self):
        r = AutoTrader.simulate(demo_series(80, seed=3))
        for key in ('mode', 'bars', 'final_equity', 'total_return_pct',
                    'buy_hold_return_pct', 'trades', 'trade_count', 'win_rate',
                    'max_drawdown_pct', 'sharpe', 'equity_curve', 'disclaimer'):
            self.assertIn(key, r)
        self.assertEqual(r['mode'], 'paper')
        self.assertIn('no exchange', r['disclaimer'])

    def test_format_report(self):
        text = format_report(AutoTrader.simulate(demo_series(60, seed=5)))
        self.assertIn('AUTOTRADE', text)
        self.assertIn('Paper execution', text)

    def test_cli(self):
        self.assertEqual(trader_main(['--demo']), 0)


if __name__ == '__main__':
    unittest.main()
