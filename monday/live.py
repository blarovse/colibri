#!/usr/bin/env python3
"""
Jarvis live loop — autonomous trading against LIVE testnet prices.

Two execution modes:
  default        paper fills only (live prices, simulated account)
  --execute      paper fills + mirrored MARKET orders on the Binance SPOT
                 TESTNET (requires your own testnet keys in
                 monday/config/secrets.env — see brokers.py)

The testnet is a sandbox with fake funds: real API mechanics, real order
lifecycles, zero real money. Mainnet is refused at every layer.

Usage:
    python -m monday.live                          # paper, BTCUSDT 1m
    python -m monday.live --symbol ETHUSDT --interval 5m
    python -m monday.live --execute                # + real testnet orders
    python -m monday.live --bars 30                # auto-stop after 30 bars

Ctrl-C disarms, flattens and prints the full report.
"""

from typing import Callable, Dict, Any, Optional, Tuple
import argparse
import sys
import time

from .agents.prediction_agent import PredictionAgent
from .brokers import (BinanceTestnetClient, BrokerError, SafetyError,
                      make_testnet_client)
from .trader import AutoTrader, PaperBroker, TraderConfig, format_report, PAPER_NOTE

LIVE_NOTE = ('Live testnet prices. ' + PAPER_NOTE)


class MirroredPaperBroker(PaperBroker):
    """
    Paper accounting first; every fill is mirrored as a MARKET order on the
    testnet. Mirror failures warn but never stop the trading loop.
    """

    def __init__(self, config: TraderConfig, client: BinanceTestnetClient,
                 symbol: str):
        super().__init__(config)
        self.client = client
        self.symbol = symbol
        self.mirrored_orders: list = []

    def _mirror(self, side: str, quantity: float, note: str) -> None:
        try:
            order = self.client.place_market_order(self.symbol, side, quantity)
            self.mirrored_orders.append(order)
            print(f'    ⚡ testnet {side} filled (orderId '
                  f'{order.get("orderId", "?")}) — {note}')
        except BrokerError as e:
            print(f'    ⚠ testnet mirror failed ({e}) — paper books unaffected')

    def buy(self, index: int, price: float):
        pos = super().buy(index, price)
        if pos is not None:
            self._mirror('BUY', pos.quantity, 'entry mirror')
        return pos

    def close(self, index: int, price: float, reason: str):
        pos = self.position
        trade = super().close(index, price, reason)
        if trade is not None:
            self._mirror('SELL', trade.quantity, f'{reason} mirror')
        return trade


class LiveRunner:
    """
    Drives an AutoTrader from a live price feed.

        runner = LiveRunner(trader, fetch_closed_bar, poll_sec)
        runner.seed(n)      # backfill n closed bars (unarmed)
        trader.arm()
        runner.run(max_bars)
    """

    def __init__(self, trader: AutoTrader,
                 fetch_closed_bar: Callable[[], Tuple[int, float]],
                 poll_seconds: float = 20.0,
                 on_event: Optional[Callable[[str], None]] = None):
        self.trader = trader
        self.fetch_closed_bar = fetch_closed_bar
        self.poll_seconds = poll_seconds
        self.on_event = on_event or print
        self._seen_open_time: Optional[int] = None
        self.bars_processed = 0

    def seed(self, bars: int = 60) -> int:
        """Backfill history without trading (trader stays disarmed)."""
        seeded = 0
        for _ in range(bars):
            try:
                open_time, close = self.fetch_closed_bar()
            except BrokerError as e:
                self.on_event(f'⚠ feed error during seed: {e}')
                break
            if open_time == self._seen_open_time:
                break
            self._seen_open_time = open_time
            self.trader.on_bar(len(self.trader.prices), close)
            seeded += 1
        self.on_event(f'◆ seeded {seeded} bars of history '
                      f'(last close {self.trader.prices[-1] if self.trader.prices else "?"})')
        return seeded

    def run(self, max_bars: Optional[int] = None,
            max_seconds: Optional[float] = None) -> Dict[str, Any]:
        """Poll the feed; feed each NEW closed bar to the armed trader."""
        started = time.time()
        try:
            while True:
                if max_bars is not None and self.bars_processed >= max_bars:
                    self.on_event(f'◆ reached {max_bars} bars — stopping')
                    break
                if max_seconds is not None and time.time() - started >= max_seconds:
                    self.on_event('◆ time limit reached — stopping')
                    break
                try:
                    open_time, close = self.fetch_closed_bar()
                except BrokerError as e:
                    self.on_event(f'⚠ feed error: {e} — retrying')
                    time.sleep(self.poll_seconds)
                    continue
                if open_time != self._seen_open_time:
                    self._seen_open_time = open_time
                    index = len(self.trader.prices)
                    action = self.trader.on_bar(index, close)
                    self.bars_processed += 1
                    equity = self.trader.broker.equity(close)
                    stamp = time.strftime('%H:%M:%S')
                    self.on_event(f'[{stamp}] bar {close:g} · equity {equity:,.0f}'
                                  + (f' · {action}' if action else ''))
                time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            self.on_event('◆ interrupted — disarming')
        self.trader.disarm(flatten=True)
        return self.trader.report()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='monday.live',
        description='Jarvis live loop — autonomous trading on LIVE testnet '
                    'prices (paper fills by default; --execute mirrors orders '
                    'to the Binance spot TESTNET).',
    )
    parser.add_argument('--symbol', default='BTCUSDT')
    parser.add_argument('--interval', default='1m',
                        choices=['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'])
    parser.add_argument('--equity', type=float, default=10_000.0)
    parser.add_argument('--fraction', type=float, default=0.10)
    parser.add_argument('--confidence', type=float, default=0.60)
    parser.add_argument('--poll', type=float, default=20.0,
                        help='seconds between feed checks')
    parser.add_argument('--seed', type=int, default=60,
                        help='history bars to backfill before arming')
    parser.add_argument('--bars', type=int, default=None,
                        help='stop after this many NEW bars')
    parser.add_argument('--execute', action='store_true',
                        help='mirror every fill as a MARKET order on the '
                             'Binance SPOT TESTNET (needs testnet keys)')
    args = parser.parse_args(argv)

    client = make_testnet_client()
    if client is None:
        if args.execute:
            print('✗ --execute needs testnet keys. Put BINANCE_TESTNET_KEY and '
                  'BINANCE_TESTNET_SECRET in monday/config/secrets.env '
                  '(free keys: https://testnet.binance.vision).')
            return 1
        # anonymous client: public market data works without keys on testnet
        client = BinanceTestnetClient(key='', secret='')

    config = TraderConfig(starting_equity=args.equity,
                          position_fraction=args.fraction,
                          confidence_min=args.confidence)

    broker: PaperBroker
    if args.execute:
        broker = MirroredPaperBroker(config, client, args.symbol)
        print('◆ EXECUTION MODE: paper books + REAL orders on the spot TESTNET '
              '(fake funds, real mechanics)')
    else:
        broker = PaperBroker(config)
        print('◆ EXECUTION MODE: paper only (live testnet prices, simulated fills)')

    trader = AutoTrader(config, agent=PredictionAgent(), broker=broker)

    def fetch_closed_bar() -> Tuple[int, float]:
        klines = client.klines(args.symbol, args.interval, limit=3)
        closed = klines[-2]  # last fully-closed candle
        return closed['open_time'], closed['close']

    runner = LiveRunner(trader, fetch_closed_bar, poll_seconds=args.poll)
    print(f'◆ {args.symbol} · {args.interval} candles · poll {args.poll:g}s · '
          f'paper equity {args.equity:,.0f}')
    print('◆ Ctrl-C to disarm and report\n')

    try:
        client.price(args.symbol)  # connectivity sanity check
    except BrokerError as e:
        print(f'✗ cannot reach the testnet feed: {e}')
        return 1

    runner.seed(args.seed)
    trader.arm()
    print('◆ ARMED — Jarvis is trading on its own now\n')
    report = runner.run(max_bars=args.bars)

    print()
    print(format_report(report))
    if isinstance(broker, MirroredPaperBroker):
        print(f'◆ testnet orders placed: {len(broker.mirrored_orders)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
