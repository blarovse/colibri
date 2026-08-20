"""Tests for broker connectivity, the live runner and safety guards (no network)."""

import io
import os
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from monday import brokers  # noqa: E402
from monday.brokers import (  # noqa: E402
    BinanceTestnetClient, BrokerError, SafetyError, load_secrets,
    load_testnet_credentials,
)
from monday.live import LiveRunner, MirroredPaperBroker  # noqa: E402
from monday.trader import AutoTrader, PaperBroker, TraderConfig  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        import json
        return json.dumps(self._payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class CapturingClient:
    """Stand-in for BinanceTestnetClient that records orders, never fails."""

    def __init__(self):
        self.orders = []

    def place_market_order(self, symbol, side, quantity):
        self.orders.append({'symbol': symbol, 'side': side,
                            'quantity': round(quantity, 5)})
        return {'orderId': len(self.orders)}


class TestSecrets(unittest.TestCase):
    def test_load_secrets_parses(self):
        with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False) as fh:
            fh.write('# comment\n\nBINANCE_TESTNET_KEY=abc\n'
                     'BINANCE_TESTNET_SECRET=def =:xyz\nOTHER=1\n')
            path = fh.name
        try:
            secrets = load_secrets(pathlib.Path(path))
            self.assertEqual(secrets['BINANCE_TESTNET_KEY'], 'abc')
            self.assertIn('def', secrets['BINANCE_TESTNET_SECRET'])
        finally:
            os.unlink(path)

    def test_credentials_missing(self):
        self.assertIsNone(load_testnet_credentials(pathlib.Path('/nonexistent')))

    def test_credentials_placeholder_rejected(self):
        with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False) as fh:
            fh.write('BINANCE_TESTNET_KEY=your_testnet_api_key_here\n'
                     'BINANCE_TESTNET_SECRET=whatever\n')
            path = fh.name
        try:
            self.assertIsNone(load_testnet_credentials(pathlib.Path(path)))
        finally:
            os.unlink(path)


class TestSandboxGuard(unittest.TestCase):
    def test_mainnet_refused(self):
        for host in brokers._MAINNET_HOSTS:
            with self.assertRaises(SafetyError):
                BinanceTestnetClient('k', 's', base_url=f'https://{host}')

    def test_random_host_refused(self):
        with self.assertRaises(SafetyError):
            BinanceTestnetClient('k', 's', base_url='https://evil.example.com')

    def test_testnet_accepted(self):
        client = BinanceTestnetClient('k', 's')
        self.assertIn('testnet.binance.vision', client.base_url)


class TestClientRequests(unittest.TestCase):
    """HTTP plumbing with urlopen monkeypatched — no network."""

    def setUp(self):
        self.client = BinanceTestnetClient('KEY123', 'SECRET456')
        self.captured = {}

    def _patch(self, payload):
        def fake_urlopen(req, timeout=None):
            self.captured = {'url': req.full_url, 'headers': dict(req.headers)}
            return FakeResponse(payload)
        self._orig = brokers.urllib.request.urlopen
        brokers.urllib.request.urlopen = fake_urlopen
        self.addCleanup(setattr, brokers.urllib.request, 'urlopen', self._orig)

    def test_price(self):
        self._patch({'symbol': 'BTCUSDT', 'price': '44000.01'})
        self.assertEqual(self.client.price('BTCUSDT'), 44000.01)
        self.assertIn('/api/v3/ticker/price', self.captured['url'])

    def test_klines_parse(self):
        rows = [[1700000000000, '100', '110', '90', '105.5', '1',
                 1700000059999], [1700000060000, '105', '111', '95', '107',
                                  '2', 1700000119999]]
        self._patch(rows)
        klines = self.client.klines('BTCUSDT', '1m', limit=2)
        self.assertEqual(len(klines), 2)
        self.assertEqual(klines[-1]['close'], 107.0)
        self.assertEqual(klines[0]['open_time'], 1700000000000)

    def test_signed_order_signature(self):
        self._patch({'symbol': 'BTCUSDT', 'orderId': 1, 'status': 'FILLED'})
        result = self.client.place_market_order('BTCUSDT', 'buy', 0.0123456)
        self.assertEqual(result['orderId'], 1)

        url = self.captured['url']
        self.assertIn('https://testnet.binance.vision/api/v3/order', url)
        query = url.split('?', 1)[1]
        params = dict(p.split('=', 1) for p in query.split('&'))
        # signature must be the exact HMAC-SHA256 of everything before it
        import hmac, hashlib, urllib.parse
        signed_part = query[:query.index('&signature=')]
        expected = hmac.new(b'SECRET456', signed_part.encode(),
                            hashlib.sha256).hexdigest()
        self.assertEqual(params['signature'], expected)
        self.assertEqual(params['side'], 'BUY')
        self.assertEqual(params['type'], 'MARKET')
        self.assertEqual(params['quantity'], '0.01235')
        self.assertEqual(self.captured['headers'].get('X-mbx-apikey')
                         or self.captured['headers'].get('X-MBX-APIKEY'), 'KEY123')

    def test_zero_quantity_rejected_locally(self):
        with self.assertRaises(BrokerError):
            self.client.place_market_order('BTCUSDT', 'BUY', 0)


class TestMirroredBroker(unittest.TestCase):
    def test_mirror_on_buy_and_close(self):
        capturing = CapturingClient()
        cfg = TraderConfig(starting_equity=10_000, warmup=0)
        broker = MirroredPaperBroker(cfg, capturing, 'BTCUSDT')
        pos = broker.buy(0, 100.0)
        self.assertIsNotNone(pos)
        self.assertEqual(len(capturing.orders), 1)
        self.assertEqual(capturing.orders[0]['side'], 'BUY')
        trade = broker.close(1, 105.0, 'take_profit')
        self.assertIsNotNone(trade)
        self.assertEqual(len(capturing.orders), 2)
        self.assertEqual(capturing.orders[1]['side'], 'SELL')

    def test_mirror_failure_does_not_break_paper(self):
        class FailingClient:
            def place_market_order(self, *a, **k):
                raise BrokerError('boom')

        cfg = TraderConfig(starting_equity=10_000)
        broker = MirroredPaperBroker(cfg, FailingClient(), 'BTCUSDT')
        pos = broker.buy(0, 100.0)
        self.assertIsNotNone(pos)  # paper fill still happened
        buf = io.StringIO()
        with redirect_stdout(buf):
            trade = broker.close(1, 101.0, 'manual')
        self.assertIsNotNone(trade)


class TestLiveRunner(unittest.TestCase):
    def _make(self, **cfg_over):
        cfg = TraderConfig(starting_equity=1_000, warmup=3, **cfg_over)
        trader = AutoTrader(cfg)
        return trader

    def test_seed_and_run_report(self):
        trader = self._make()
        prices = iter([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
        state = {'t': 0}

        def fetch():
            state['t'] += 60_000
            return state['t'], next(prices)

        events = []
        runner = LiveRunner(trader, fetch, poll_seconds=0)
        seeded = runner.seed(3)
        self.assertEqual(seeded, 3)
        self.assertEqual(len(trader.prices), 3)
        trader.arm()
        report = runner.run(max_bars=3)
        self.assertEqual(runner.bars_processed, 3)
        self.assertEqual(report['bars'], 6)
        self.assertFalse(report['armed'])  # disarmed at the end

    def test_duplicate_bars_ignored(self):
        trader = self._make()
        fetches = [(1, 100.0), (1, 100.0), (2, 101.0), (2, 101.0)]
        fetch = iter(fetches).__next__
        runner = LiveRunner(trader, fetch, poll_seconds=0)
        runner.seed(1)
        trader.arm()
        runner.run(max_bars=1)
        self.assertEqual(len(trader.prices), 2)  # only unique bars counted


if __name__ == '__main__':
    unittest.main()
