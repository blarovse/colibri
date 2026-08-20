#!/usr/bin/env python3
"""
Jarvis AutoTrader — autonomous trading on command.

Arms on your command, then trades completely on its own:
signal -> risk check -> position sizing -> execution -> exits -> P&L.

MODE IS PAPER BY DEFAULT. Fills are simulated against the price series you
feed it (commission + slippage modeled). No exchange is contacted, no keys
exist in this module, and real-money trading is intentionally not
implemented. If you ever wire a live broker yourself: run it against a
testnet first, keep the risk limits, and remember the backtest often
reports "no measurable edge".

Usage:
    python -m monday.trader prices.csv            # auto-trade the series
    python -m monday.trader --demo                # seeded demo
    from monday.trader import AutoTrader, TraderConfig
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
import argparse
import math
import re
import sys

from .agents.prediction_agent import PredictionAgent

PAPER_NOTE = (
    'Paper execution only — simulated fills, no exchange contacted, no real '
    'money. Past (simulated) performance never guarantees future results.'
)


@dataclass
class TraderConfig:
    """Risk limits and execution parameters. Deliberately conservative."""
    starting_equity: float = 10_000.0
    position_fraction: float = 0.10      # each entry risks 10% of equity
    confidence_min: float = 0.60         # only act when Jarvis is this sure
    prob_min: float = 0.60               # and P(up) at least this
    stop_loss_pct: float = 0.03          # exit if trade drops 3%
    take_profit_pct: float = 0.06        # exit if trade rises 6%
    commission_bps: float = 10.0         # 0.10% per fill
    slippage_bps: float = 5.0            # 0.05% adverse slippage per fill
    max_drawdown_kill: float = 0.20      # halt everything at -20% equity
    max_consecutive_losses: int = 5      # halt after 5 losers in a row
    warmup: int = 12                     # bars before trading starts
    allow_short: bool = False            # long-only by default


@dataclass
class Position:
    side: str                            # 'long' (shorts off by default)
    entry_index: int
    entry_price: float
    quantity: float
    stop_price: float
    target_price: float


@dataclass
class Trade:
    side: str
    entry_index: int
    entry_price: float
    exit_index: int
    exit_price: float
    quantity: float
    pnl: float
    reason: str                          # signal_flip | stop_loss | take_profit | end_of_data | manual


class PaperBroker:
    """
    Simulated broker: cash, one position at a time, commission + slippage.

    Accounting invariant: equity == cash + quantity * price at all times.
    """

    def __init__(self, config: TraderConfig):
        self.config = config
        self.cash = config.starting_equity
        self.position: Optional[Position] = None
        self.realized_pnl = 0.0
        self.fills = 0

    def _costs(self, price: float, quantity: float) -> float:
        return price * quantity * (self.config.commission_bps / 10_000.0)

    def buy(self, index: int, price: float) -> Optional[Position]:
        """Open a long position sized by config; None if it can't."""
        if self.position is not None:
            return None
        slipped = price * (1 + self.config.slippage_bps / 10_000.0)
        if slipped <= 0 or self.cash <= 0:
            return None
        budget = min(self.cash * self.config.position_fraction, self.cash)
        qty = budget / slipped
        # shave the size until cost incl. commission fits inside the budget
        while qty > 0:
            cost = qty * slipped + self._costs(slipped, qty)
            if cost <= budget * 1.0000001:
                break
            qty *= 0.999
        cost = qty * slipped + self._costs(slipped, qty)
        if qty <= 0 or cost > self.cash:
            return None
        self.cash -= cost
        self.fills += 1
        self.position = Position(
            side='long', entry_index=index, entry_price=slipped, quantity=qty,
            stop_price=slipped * (1 - self.config.stop_loss_pct),
            target_price=slipped * (1 + self.config.take_profit_pct),
        )
        return self.position

    def close(self, index: int, price: float, reason: str) -> Optional[Trade]:
        """Close the open position at price (with slippage)."""
        pos = self.position
        if pos is None:
            return None
        slipped = price * (1 - self.config.slippage_bps / 10_000.0)
        proceeds = slipped * pos.quantity - self._costs(slipped, pos.quantity)
        self.cash += proceeds
        self.fills += 1
        pnl = proceeds - (pos.entry_price * pos.quantity +
                          self._costs(pos.entry_price, pos.quantity))
        self.realized_pnl += pnl
        self.position = None
        return Trade(side=pos.side, entry_index=pos.entry_index,
                     entry_price=pos.entry_price, exit_index=index,
                     exit_price=slipped, quantity=pos.quantity,
                     pnl=round(pnl, 4), reason=reason)

    def equity(self, price: float) -> float:
        if self.position is None:
            return self.cash
        return self.cash + self.position.quantity * price


class AutoTrader:
    """
    The autonomous loop. One public method per lifecycle step:

        arm()          -> enable trading (nothing happens before this)
        on_bar(i, p)   -> feed bar i at price p; Jarvis decides & acts alone
        disarm()       -> stop trading (flat the position when asked)
    """

    def __init__(self, config: Optional[TraderConfig] = None,
                 agent: Optional[PredictionAgent] = None):
        self.config = config or TraderConfig()
        self.agent = agent or PredictionAgent()
        self.broker = PaperBroker(self.config)
        self.armed = False
        self.killed = False
        self.kill_reason = ''
        self.consecutive_losses = 0
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.peak_equity = self.config.starting_equity
        self.prices: List[float] = []
        self.actions: List[str] = []

    # -- lifecycle ------------------------------------------------------

    def arm(self) -> str:
        self.armed = True
        self.actions.append('ARMED — autonomous paper trading enabled')
        return 'Armed, sir. I will trade the next qualifying signal on my own.'

    def disarm(self, flatten: bool = True) -> str:
        if flatten and self.broker.position is not None and self.prices:
            trade = self.broker.close(len(self.prices) - 1,
                                      self.prices[-1], 'manual')
            if trade:
                self._record(trade)
        self.armed = False
        self.actions.append('DISARMED')
        return 'Disarmed, sir. Standing down.'

    # -- the autonomous brain ------------------------------------------

    def on_bar(self, index: int, price: float) -> Optional[str]:
        """Process one bar: manage exits, then look for a new entry."""
        self.prices.append(price)
        equity = self.broker.equity(price)
        self.equity_curve.append(round(equity, 4))
        self.peak_equity = max(self.peak_equity, equity)

        # 1) risk-of-ruin checks run even when unarmed if a position exists
        if self.broker.position is not None:
            drawdown = 1 - equity / self.peak_equity
            if drawdown >= self.config.max_drawdown_kill:
                self._kill('max drawdown breached')
                return 'KILL SWITCH: drawdown limit hit — flattened and halted.'

        if self.killed or not self.armed or index < self.config.warmup:
            return None

        # 2) manage the open position
        pos = self.broker.position
        if pos is not None:
            reason = None
            if price <= pos.stop_price:
                reason = 'stop_loss'
            elif price >= pos.target_price:
                reason = 'take_profit'
            if reason:
                trade = self.broker.close(index, price, reason)
                if trade:
                    self._record(trade)
                    return f'EXITED ({reason}) at {trade.exit_price:g} — P&L {trade.pnl:+g}.'

        # 3) flip on a confident opposite signal
        if pos is not None:
            pred = self._predict()
            if pred and pred['verdict'] == 'DOWN' and \
                    pred['confidence'] >= self.config.confidence_min:
                trade = self.broker.close(index, price, 'signal_flip')
                if trade:
                    self._record(trade)
                    return f'EXITED (signal flip) at {trade.exit_price:g} — P&L {trade.pnl:+g}.'

        # 4) look for a new entry
        if self.broker.position is None and not self.killed:
            pred = self._predict()
            if pred and pred['verdict'] == 'UP' and \
                    pred['confidence'] >= self.config.confidence_min and \
                    pred['probabilities']['up'] >= self.config.prob_min:
                opened = self.broker.buy(index, price)
                if opened:
                    return (f'ENTERED long {opened.quantity:.4g} @ '
                            f'{opened.entry_price:g} (stop {opened.stop_price:g}, '
                            f'target {opened.target_price:g}).')
        return None

    def _predict(self) -> Optional[Dict[str, Any]]:
        if len(self.prices) < 6:
            return None
        return self.agent.predict_direction(self.prices)

    def _kill(self, reason: str) -> None:
        self.killed = True
        self.kill_reason = reason
        if self.broker.position is not None and self.prices:
            trade = self.broker.close(len(self.prices) - 1, self.prices[-1],
                                      'manual')
            if trade:
                self._record(trade)
        self.armed = False
        self.actions.append(f'KILL SWITCH: {reason}')

    def _record(self, trade: Trade) -> None:
        self.trades.append(trade)
        if trade.pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.config.max_consecutive_losses:
                self._kill(f'{self.consecutive_losses} consecutive losses')
        else:
            self.consecutive_losses = 0

    # -- reporting ------------------------------------------------------

    def report(self) -> Dict[str, Any]:
        """Full stats for the run."""
        curve = self.equity_curve or [self.config.starting_equity]
        final = curve[-1]
        total_return = final / self.config.starting_equity - 1

        # buy & hold comparison over the traded window
        bh_return = 0.0
        if len(self.prices) >= 2 and self.prices[0]:
            start_i = min(self.config.warmup, len(self.prices) - 1)
            bh_return = self.prices[-1] / self.prices[start_i] - 1

        peak, max_dd = curve[0], 0.0
        for eq in curve:
            peak = max(peak, eq)
            if peak > 0:
                max_dd = min(max_dd, eq / peak - 1)

        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        gross_win = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))

        # per-bar equity returns -> rough annualised Sharpe (daily assumption)
        rets = [(curve[i] / curve[i - 1] - 1) for i in range(1, len(curve))
                if curve[i - 1] > 0]
        sharpe = 0.0
        if len(rets) > 2:
            m = sum(rets) / len(rets)
            sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
            sharpe = (m / sd * math.sqrt(252)) if sd > 0 else 0.0

        return {
            'kind': 'autotrade',
            'mode': 'paper',
            'bars': len(self.prices),
            'armed': self.armed,
            'killed': self.killed,
            'kill_reason': self.kill_reason or None,
            'starting_equity': self.config.starting_equity,
            'final_equity': round(final, 2),
            'total_return_pct': round(total_return * 100, 2),
            'buy_hold_return_pct': round(bh_return * 100, 2),
            'open_position': asdict(self.broker.position) if self.broker.position else None,
            'trades': [asdict(t) for t in self.trades],
            'trade_count': len(self.trades),
            'win_rate': round(len(wins) / len(self.trades), 3) if self.trades else None,
            'wins': len(wins),
            'losses': len(losses),
            'profit_factor': round(gross_win / gross_loss, 2) if gross_loss > 0
            else (None if not wins else float('inf')),
            'max_drawdown_pct': round(max_dd * 100, 2),
            'sharpe': round(sharpe, 2),
            'fills': self.broker.fills,
            'realized_pnl': round(self.broker.realized_pnl, 2),
            'equity_curve': curve,
            'actions': self.actions,
            'disclaimer': PAPER_NOTE,
        }

    # -- one-shot simulation over a whole series ------------------------

    @classmethod
    def simulate(cls, series: List[float],
                 config: Optional[TraderConfig] = None) -> Dict[str, Any]:
        """Arm, trade the full series bar by bar, disarm, report."""
        trader = cls(config)
        trader.arm()
        for i, price in enumerate(series):
            trader.on_bar(i, float(price))
        trader.disarm(flatten=True)
        report = trader.report()
        report['series'] = [float(v) for v in series]
        return report


# ---------------------------------------------------------------- CLI

def format_report(r: Dict[str, Any]) -> str:
    if 'error' in r:
        return f"◆ {r['error']}"
    lines = [
        "◆ AUTOTRADE — paper simulation, Jarvis fully autonomous",
        f"  bars {r['bars']} · trades {r['trade_count']} "
        f"({r['wins']}W / {r['losses']}L"
        + (f", win rate {r['win_rate']:.0%}" if r['win_rate'] is not None else '') + ')',
        f"  equity  {r['starting_equity']:g} → {r['final_equity']:g}  "
        f"({r['total_return_pct']:+.2f}%)  ·  buy&hold {r['buy_hold_return_pct']:+.2f}%",
        f"  max DD {r['max_drawdown_pct']:.2f}% · Sharpe≈{r['sharpe']} · "
        f"profit factor {r['profit_factor'] if r['profit_factor'] != float('inf') else '∞'}",
    ]
    if r['killed']:
        lines.append(f"  ⚠ KILL SWITCH: {r['kill_reason']}")
    for t in r['trades'][-6:]:
        lines.append(f"    {t['side']:>4} in@{t['entry_price']:g} → out@{t['exit_price']:g}"
                     f"  {t['pnl']:+g}  ({t['reason']})")
    lines.append(f"  ◆ {r['disclaimer']}")
    return '\n'.join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='monday.trader',
        description='Jarvis AutoTrader — autonomous PAPER trading on a price series.',
    )
    parser.add_argument('file', nargs='?', help='CSV/TXT file with a price series')
    parser.add_argument('--demo', action='store_true', help='seeded demo series')
    parser.add_argument('--equity', type=float, default=10_000.0)
    parser.add_argument('--fraction', type=float, default=0.10,
                        help='position size as fraction of equity (default 0.10)')
    parser.add_argument('--confidence', type=float, default=0.60)
    args = parser.parse_args(argv)

    if args.demo or not args.file:
        series = __import__('monday.backtest', fromlist=['demo_series']).demo_series(250)
        print(f"◆ demo series: {len(series)} points (seeded random walk, mild drift)")
    else:
        with open(args.file, 'r', encoding='utf-8') as fh:
            series = [float(m) for m in re.findall(r'-?\d+(?:\.\d+)?', fh.read())]
        if len(series) < 20:
            print(f"need ≥20 points, got {len(series)}")
            return 1
        print(f"◆ loaded {len(series)} points from {args.file}")

    config = TraderConfig(starting_equity=args.equity, position_fraction=args.fraction,
                          confidence_min=args.confidence)
    report = AutoTrader.simulate(series, config)
    print(format_report(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
