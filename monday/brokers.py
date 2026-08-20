#!/usr/bin/env python3
"""
Broker connectivity for Jarvis — Binance SPOT TESTNET, and nothing else.

Safety properties, by construction:
- The ONLY exchange URL in this module is the testnet. There is no mainnet
  constant, no override, no env toggle. Going live means editing this file
  deliberately — and you should not.
- Keys are read from monday/config/secrets.env (gitignored) or the
  BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET environment variables.
  Keys are never logged and never accepted as function arguments from
  untrusted input.
- Everything runs on the Python standard library (urllib, hmac) — no extra
  dependencies.

Create free testnet keys: https://testnet.binance.vision
"""

from typing import Any, Dict, List, Optional
import hashlib
import hmac
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

TESTNET_BASE_URL = 'https://testnet.binance.vision'
_MAINNET_HOSTS = ('api.binance.com', 'api1.binance.com', 'api-gcp.binance.com')

SECRETS_PATH = pathlib.Path(__file__).parent / 'config' / 'secrets.env'


class BrokerError(RuntimeError):
    """Raised for any broker/network problem."""


class SafetyError(RuntimeError):
    """Raised when a request would leave the testnet sandbox."""


def load_secrets(path: Optional[pathlib.Path] = None) -> Dict[str, str]:
    """
    Parse KEY=VALUE lines from secrets.env. Comments (#) and blanks ignored.
    """
    path = pathlib.Path(path or SECRETS_PATH)
    secrets: Dict[str, str] = {}
    if not path.exists():
        return secrets
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        secrets[key.strip()] = value.strip()
    return secrets


def load_testnet_credentials(
        secrets_path: Optional[pathlib.Path] = None) -> Optional[Dict[str, str]]:
    """Return {'key':..., 'secret':...} or None if not configured."""
    secrets = load_secrets(secrets_path)
    key = os.environ.get('BINANCE_TESTNET_KEY') or secrets.get('BINANCE_TESTNET_KEY')
    secret = (os.environ.get('BINANCE_TESTNET_SECRET')
              or secrets.get('BINANCE_TESTNET_SECRET'))
    if not key or not secret or key.startswith('your_'):
        return None
    return {'key': key, 'secret': secret}


class BinanceTestnetClient:
    """
    Minimal signed client for the Binance SPOT TESTNET.

    Public (no key):   price(symbol), klines(symbol, interval, limit)
    Signed (key+secret): place_market_order(...), account()
    """

    def __init__(self, key: str, secret: str,
                 base_url: str = TESTNET_BASE_URL, timeout: float = 10.0):
        self.key = key
        self.secret = secret.encode('utf-8')
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._assert_sandbox()

    def _assert_sandbox(self) -> None:
        """Hard guard: refuse any non-testnet host, forever."""
        host = urllib.parse.urlparse(self.base_url).hostname or ''
        if host != urllib.parse.urlparse(TESTNET_BASE_URL).hostname:
            raise SafetyError(
                f'refusing host {host!r}: Jarvis brokers are TESTNET-ONLY by '
                f'design. Live trading is intentionally not supported.')

    # -- http ------------------------------------------------------------

    def _request(self, method: str, path: str,
                 params: Optional[Dict[str, Any]] = None,
                 signed: bool = False) -> Any:
        params = dict(params or {})
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['recvWindow'] = 5000
            query = urllib.parse.urlencode(params)
            signature = hmac.new(self.secret, query.encode('utf-8'),
                                 hashlib.sha256).hexdigest()
            query += f'&signature={signature}'
            url = f'{self.base_url}{path}?{query}'
            headers = {'X-MBX-APIKEY': self.key}
        else:
            query = urllib.parse.urlencode(params)
            url = f'{self.base_url}{path}' + (f'?{query}' if query else '')
            headers = {}
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300]
            raise BrokerError(f'HTTP {e.code} from {path}: {body}') from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise BrokerError(f'network error calling {path}: {e}') from e

    # -- public endpoints --------------------------------------------------

    def price(self, symbol: str) -> float:
        data = self._request('GET', '/api/v3/ticker/price', {'symbol': symbol})
        return float(data['price'])

    def klines(self, symbol: str, interval: str = '1m',
               limit: int = 100) -> List[Dict[str, Any]]:
        """Recent candles; newest LAST (may still be forming)."""
        rows = self._request('GET', '/api/v3/klines',
                             {'symbol': symbol, 'interval': interval,
                              'limit': max(2, min(limit, 500))})
        return [
            {'open_time': int(r[0]), 'open': float(r[1]), 'high': float(r[2]),
             'low': float(r[3]), 'close': float(r[4]), 'close_time': int(r[6])}
            for r in rows
        ]

    # -- signed endpoints ----------------------------------------------------

    def account(self) -> Dict[str, Any]:
        return self._request('GET', '/api/v3/account', signed=True)

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """side: 'BUY' or 'SELL'. Quantity is rounded to 5 decimals."""
        qty = round(float(quantity), 5)
        if qty <= 0:
            raise BrokerError(f'non-positive quantity {quantity}')
        return self._request('POST', '/api/v3/order', {
            'symbol': symbol, 'side': side.upper(), 'type': 'MARKET',
            'quantity': f'{qty:.5f}',
        }, signed=True)


def make_testnet_client(
        secrets_path: Optional[pathlib.Path] = None) -> Optional[BinanceTestnetClient]:
    """Build a client from secrets.env / env vars, or None if unconfigured."""
    creds = load_testnet_credentials(secrets_path)
    if not creds:
        return None
    return BinanceTestnetClient(creds['key'], creds['secret'])
