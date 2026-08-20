#!/usr/bin/env python3
"""
Jarvis — the prediction console

An interactive, Jarvis-styled front end for Monday's PredictionAgent.
It answers one class of question and refuses everything else:
*what happens next* — trading direction, series forecasts, sequence
patterns, event odds and risk.

Runs fully offline on local statistics; no API keys required.

Usage:
    python -m monday.jarvis                          # interactive session
    python -m monday.jarvis "next number in 2 4 8 16 32"
    python -m monday.jarvis "prices: 44,45,46,44.5,47" --direction --json
    python -m monday.jarvis --demo                   # guided tour
"""

from typing import Dict, Any, List, Optional
import argparse
import json
import re
import sys

from .agents.prediction_agent import PredictionAgent

BANNER = """
◈ JARVIS — prediction engine · Monday platform
  "One specialism, sir: what happens next."
  trading direction · series forecasts · sequences · event odds · risk
  Type 'help' for commands · 'quit' to leave.
"""

HELP = """Commands:
  <numbers>                     work on a series, e.g.  101 103 99 105 108
  predict|forecast              next-value forecast for the current series
  direction|up or down|trend    direction probabilities (up/down/sideways)
  scenarios|bull|bear           bull / base / bear targets
  risk|volatility               volatility, drawdown, VaR
  brief                         full market brief on the current series
  next number in 2 4 8 16       solve a sequence pattern
  odds|probability ...          event odds: "odds 7 of 10"
                                or "odds base 30% strong evidence for"
  load <file>                   load a price series (one number per line,
                                or comma/space separated)
  show                          show the current series
  reset                         clear the session
  help                          this message
  quit|exit                     leave

Notes:
  • I only predict. Anything else, I politely decline.
  • Everything I say is a transparent statistical estimate —
    never financial advice.
"""


def _numbers(text: str) -> List[float]:
    return [float(m) for m in re.findall(r'-?\d+(?:\.\d+)?', text)]


CRYPTO_ALIASES = {
    'btc': 'BTC', 'bitcoin': 'BTC', 'eth': 'ETH', 'ethereum': 'ETH',
    'sol': 'SOL', 'solana': 'SOL', 'doge': 'DOGE', 'dogecoin': 'DOGE',
    'xrp': 'XRP', 'ada': 'ADA', 'bnb': 'BNB', 'ltc': 'LTC',
}

_TICKER_RE = re.compile(r'\b([A-Z]{2,5})\b')
_TICKER_STOP = {
    'HELP', 'QUIT', 'EXIT', 'RESET', 'SHOW', 'LOAD', 'JSON', 'DEMO',
    'THE', 'AND', 'FOR', 'NEXT', 'WHAT', 'WILL', 'IT', 'GO', 'IS',
    'MY', 'ME', 'UP', 'OR', 'IN', 'OF', 'TO', 'ON', 'BE', 'DO', 'AT',
}


def _symbol_from(text: str) -> Optional[str]:
    lower = text.lower()
    for alias, symbol in CRYPTO_ALIASES.items():
        if re.search(rf'\b{alias}\b', lower):
            return symbol
    for match in _TICKER_RE.findall(text):
        if match not in _TICKER_STOP:
            return match
    return None


class JarvisConsole:
    """Interactive persona shell around the PredictionAgent."""

    def __init__(self, agent: Optional[PredictionAgent] = None):
        self.agent = agent or PredictionAgent()
        self.series: List[float] = []
        self.symbol: Optional[str] = None
        self.history: List[str] = []

    # ------------------------------------------------------------------
    # Main entry: turn free text into a Jarvis reply
    # ------------------------------------------------------------------

    def ask(self, text: str) -> str:
        """Answer a prediction request; returns formatted text."""
        text = text.strip()
        if not text:
            return "Sir?"
        low = text.lower()
        self.history.append(text)

        # --- session commands -------------------------------------------
        if low in ('quit', 'exit'):
            return "Goodbye, sir. Do mind the volatility out there."
        if low in ('help', '?'):
            return HELP
        if low == 'reset':
            self.series, self.symbol = [], None
            return "Session cleared, sir."
        if low == 'show':
            return self._show()
        if low.startswith('load'):
            return self._load(text)

        # --- capture an inline series early so commands can use it ------
        nums = _numbers(text)
        if len(nums) >= 3:
            self.series = nums
            symbolic = _symbol_from(text)
            if symbolic:
                self.symbol = symbolic

        # --- event probability ------------------------------------------
        if any(w in low for w in ('odds', 'probab', 'chance', 'likel')):
            reply = self._event(text)
            if reply:
                return reply

        # --- explicit commands ------------------------------------------
        if low in ('direction', 'trend', 'up', 'down', 'bull', 'bear'):
            return self._direction()
        if 'scenario' in low or 'bull' in low or 'bear' in low:
            return self._scenarios()
        if low in ('risk', 'volatility', 'vol'):
            return self._risk()
        if low == 'brief':
            return self._brief()
        if low.startswith(('autotrade', 'auto trade', 'auto-trade')):
            return self._autotrade(text)

        # --- sequence / series work --------------------------------------
        wants_sequence = bool(
            re.search(r'next (number|term|value|digit)', low)
            or 'sequence' in low or 'pattern' in low
        )
        wants_direction = any(w in low for w in (
            'direction', 'up or down', 'will it', 'go up', 'go down',
            'rise', 'fall', 'drop', 'rally', 'trend', 'market', 'trade',
            'tomorrow', 'next bar', 'next candle')) \
            or bool(re.search(r'what will .* (do|go)', low))
        wants_forecast = any(w in low for w in (
            'forecast', 'predict', 'next value', 'next', 'projection', 'outlook'))

        if len(nums) >= 3:
            wants_point = bool(re.search(r'next (number|term|value)', low)) or 'forecast' in low
            if wants_sequence and all(float(v).is_integer() for v in nums):
                return self._sequence()
            if wants_point and not wants_direction:
                return self._auto_forecast()
            if wants_direction:
                return self._direction()
            return self._auto_forecast()

        if self.series:
            # operate on the loaded series
            if wants_direction:
                return self._direction()
            if wants_sequence:
                return self._sequence()
            if 'risk' in low or 'volatil' in low:
                return self._risk()
            if wants_forecast:
                return self._auto_forecast()

        # --- off topic ----------------------------------------------------
        return (
            "I'm afraid I only concern myself with one thing, sir: "
            "what happens next. Give me a series of numbers, a sequence "
            "puzzle, or an event whose odds you want — or type 'help'."
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _auto_forecast(self) -> str:
        if not self.series:
            return "I have no series to work from, sir. Paste numbers or 'load <file>'."
        seq = self.agent.predict_sequence(self.series)
        if seq.get('pattern', 'none') != 'none':
            return self._sequence()
        forecast = self.agent.forecast_series(self.series)
        return self._format_forecast(forecast)

    def _sequence(self) -> str:
        if not self.series:
            return "No sequence loaded, sir. Try: next number in 2 4 8 16 32"
        result = self.agent.predict_sequence(self.series)
        if 'error' in result:
            return result['error']
        if result.get('pattern') == 'none':
            return self._format_forecast(result)
        lines = [f"◆ Pattern:   {result['pattern'].replace('_', ' ')}"]
        if result.get('detail'):
            lines.append(f"◆ Rule:      {result['detail']}")
        lines.append(f"◆ Next term: {result['next_value']:g}")
        lines.append(f"◆ Confidence: {result['confidence']:.0%}")
        return "\n".join(lines)

    def _direction(self) -> str:
        if not self.series:
            return self._no_series("direction")
        result = self.agent.predict_direction(self.series, symbol=self.symbol)
        if 'error' in result:
            return result['error']
        return self._format_direction(result)

    def _scenarios(self) -> str:
        if not self.series:
            return self._no_series("scenarios")
        result = self.agent.scenarios(self.series, symbol=self.symbol)
        if 'error' in result:
            return result['error']
        lines = [f"◆ Scenarios for {result['symbol']} (last {result['last_value']:g}):"]
        for sc in result['scenarios']:
            lines.append(
                f"  {sc['name']:>4}: {sc['target']:g}  ({sc['change_pct']:+.2f}%)  "
                f"p={sc['probability']:.0%}"
            )
        lines.append(f"◆ Confidence: {result['confidence']:.0%}")
        lines.append(f"◆ {result['disclaimer']}")
        return "\n".join(lines)

    def _risk(self) -> str:
        if not self.series:
            return self._no_series("risk")
        result = self.agent.assess_risk(self.series, symbol=self.symbol)
        if 'error' in result:
            return result['error']
        lines = [
            f"◆ Risk: {result['risk_label'].upper()}  (score {result['risk_score']}/10)",
            f"◆ Volatility: {result['volatility_per_period']:.3%} per period "
            f"(≈{result['annualized_volatility_pct']:.1f}% annualised, daily bars)",
            f"◆ Max drawdown: {result['max_drawdown_pct']:.2f}%",
            f"◆ Historical VaR 95%: {result['historical_var_95_pct']:.2f}% per period",
            f"◆ Vol regime: {result['volatility_regime']} · trend R² {result['trend_stability_r2']:.2f}",
        ]
        for w in result.get('warnings', []):
            lines.append(f"◆ ⚠ {w}")
        lines.append(f"◆ {result['disclaimer']}")
        return "\n".join(lines)

    @staticmethod
    def _no_series(what: str) -> str:
        return (f"I need numbers before I can judge {what}, sir. "
                f"Paste a series or 'load <file>' first.")

    def _autotrade(self, text: str) -> str:
        """Run the autonomous paper trader over the current series."""
        if not self.series:
            return self._no_series("auto-trading")
        from .trader import AutoTrader, TraderConfig, format_report
        config = TraderConfig()
        # optional equity override: "autotrade with 5000"
        import re as _re
        m = _re.search(r'(\d+(?:\.\d+)?)\s*(?:equity|capital|usd|\$)?', text)
        if m and float(m.group(1)) >= 100:
            config.starting_equity = float(m.group(1))
        report = AutoTrader.simulate(self.series, config)
        return format_report(report)

    def _brief(self) -> str:
        if not self.series:
            return self._no_series("a brief")
        result = self.agent.analyze_market(self.series, symbol=self.symbol)
        if 'error' in result:
            return result['error']
        d = self._format_direction(result['direction'], header=False)
        lines = [f"◆ Market brief — {result['symbol']}"] + [d]
        for sc in result['scenarios']:
            lines.append(
                f"  {sc['name']:>4}: {sc['target']:g} ({sc['change_pct']:+.2f}%) p={sc['probability']:.0%}"
            )
        risk = result['risk']
        lines.append(
            f"◆ Risk {risk['risk_label']} ({risk['risk_score']}/10) · "
            f"VaR95 {risk['historical_var_95_pct']:.2f}% · RSI "
            f"{result['indicators']['rsi']:.1f}" if result['indicators']['rsi'] is not None
            else f"◆ Risk {risk['risk_label']} ({risk['risk_score']}/10)"
        )
        lines.append(f"◆ {result['disclaimer']}")
        return "\n".join(lines)

    def _event(self, text: str) -> Optional[str]:
        low = text.lower()

        # frequency form: "7 of 10", "7 out of 10", "7/10", "7 in 10"
        m = re.search(r'(\d+)\s*(?:/|out of|of|in)\s*(\d+)', low)
        if m and int(m.group(2)) > 0:
            k, n = int(m.group(1)), int(m.group(2))
            if k <= n:
                result = self.agent.event_probability(successes=k, trials=n)
                lines = [f"◆ Probability: {result['probability']:.1%}",
                         f"◆ 95% interval: [{result['interval_95'][0]:.1%}, "
                         f"{result['interval_95'][1]:.1%}]"]
                lines.extend(f"◆ {s}" for s in result['reasoning'])
                return "\n".join(lines)

        # base-rate form: "odds base 30% with strong evidence for"
        m = re.search(r'base(?:\s*rate)?\s*([0-9]*\.?[0-9]+)\s*%?', low)
        if m:
            pct = float(m.group(1))
            base_rate = pct / 100.0 if pct > 1.0 else pct
            evidence = self._parse_evidence(low)
            result = self.agent.event_probability(
                base_rate=base_rate, evidence=evidence)
            lines = [f"◆ Probability: {result['probability_pct']:.1f}%"]
            lines.extend(f"◆ {s}" for s in result['reasoning'])
            return "\n".join(lines)

        return (
            "To judge odds I need numbers, sir. Try:\n"
            "  odds 7 of 10                      (observed frequency)\n"
            "  odds base 30% strong evidence for (base rate + evidence)"
        )

    @staticmethod
    def _parse_evidence(low: str) -> List[Dict[str, Any]]:
        strength_map = {'strong': 0.9, 'solid': 0.7, 'moderate': 0.5,
                        'weak': 0.3, 'slight': 0.2}
        evidence = []
        for chunk in re.split(r',| and (?=strong|solid|moderate|weak|slight)', low):
            chunk = chunk.strip()
            direction = 'against' if 'against' in chunk or 'oppos' in chunk or 'negative' in chunk else 'for'
            strength = 0.5
            for word, value in strength_map.items():
                if word in chunk:
                    strength = value
                    break
            if any(w in chunk for w in ('evidence', 'argument', 'signal', 'sign of', 'data point')) or \
               any(w in chunk for w in strength_map):
                evidence.append({'direction': direction, 'strength': strength})
        return evidence

    def _json_default(self, question: str) -> Dict[str, Any]:
        """Machine-readable dispatch for one-shot --json mode."""
        if not self.series:
            return {'error': 'no series'}
        low = question.lower()
        if re.search(r'next (number|term|value)', low) or 'sequence' in low or 'pattern' in low:
            return self.agent.predict_sequence(self.series)
        if 'scenario' in low or 'bull' in low or 'bear' in low:
            return self.agent.scenarios(self.series, symbol=self.symbol)
        if 'risk' in low or 'volatil' in low:
            return self.agent.assess_risk(self.series, symbol=self.symbol)
        seq = self.agent.predict_sequence(self.series)
        if seq.get('pattern', 'none') != 'none':
            return seq
        return self.agent.forecast_series(self.series)

    def _load(self, text: str) -> str:
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return "Which file, sir? Usage: load <path>"
        path = parts[1].strip().strip('"\'')
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                content = fh.read()
        except OSError as e:
            return f"I can't read that file, sir: {e}"
        nums = _numbers(content)
        if len(nums) < 3:
            return "That file has fewer than three numbers, sir — not enough to forecast."
        self.series = nums
        self.symbol = self.symbol
        return (f"◆ Loaded {len(nums)} points "
                f"({_fmt_num(nums[0])} … {_fmt_num(nums[-1])}). "
                f"Ask away: 'direction', 'forecast', 'scenarios', 'risk'.")

    def _show(self) -> str:
        if not self.series:
            return "Nothing loaded, sir."
        preview = ', '.join(_fmt_num(v) for v in self.series[:12])
        more = f" … (+{len(self.series) - 12} more)" if len(self.series) > 12 else ''
        return (f"◆ Series: {preview}{more}\n"
                f"◆ Symbol: {self.symbol or 'unlabelled'} · {len(self.series)} points")

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_direction(self, r: Dict[str, Any], header: bool = True) -> str:
        p = r['probabilities']
        lines = []
        if header:
            lines.append(f"◆ {r['symbol']} at {_fmt_num(r['last_value'])} — next move:")
        lines.append(
            f"◆ Verdict: {r['verdict']}   "
            f"(up {p['up']:.0%} · down {p['down']:.0%} · sideways {p['sideways']:.0%})"
        )
        lines.append(f"◆ Expected move: {r['expected_move_pct']:+.2f}% · "
                     f"confidence {r['confidence']:.0%}")
        reads = ', '.join(
            f"{s['name']} {s['reading']}" for s in r['signals']
            if s['reading'] != 'neutral'
        ) or 'all signals neutral'
        lines.append(f"◆ Signals: {reads}")
        levels = []
        if r.get('support') is not None:
            levels.append(f"support {_fmt_num(r['support'])}")
        if r.get('resistance') is not None:
            levels.append(f"resistance {_fmt_num(r['resistance'])}")
        if levels:
            lines.append(f"◆ Levels: {' · '.join(levels)}")
        lines.append(f"◆ {r['disclaimer']}")
        return "\n".join(lines)

    def _format_forecast(self, r: Dict[str, Any]) -> str:
        lines = [
            f"◆ Next value: {_fmt_num(r['next_value'])} "
            f"(horizon {r['horizon']}, trend {r['trend']})",
            f"◆ 80% range: [{_fmt_num(r['interval_80'][0])}, {_fmt_num(r['interval_80'][1])}]",
            f"◆ 95% range: [{_fmt_num(r['interval_95'][0])}, {_fmt_num(r['interval_95'][1])}]",
            f"◆ Confidence: {r['confidence']:.0%} · engines "
            + ', '.join(f"{k} {v:.0%}" for k, v in r['engine_weights'].items()),
        ]
        if r.get('disclaimer'):
            lines.append(f"◆ {r['disclaimer']}")
        return "\n".join(lines)


def _fmt_num(v: float) -> str:
    return f"{v:g}" if abs(v) < 1e12 else f"{v:.4g}"


DEMO_SCRIPT = [
    ("next number in 2 4 8 16 32 64", "A sequence, sir. Trivial."),
    ("prices: 100.2 101.1 99.8 100.9 101.7 102.4 101.9 102.8 103.5 103.1 104.2 105.0",
     "Now a market series."),
    ("direction", "Which way is it headed?"),
    ("scenarios", "Let's frame the outcomes."),
    ("risk", "And what could go wrong."),
    ("odds 7 of 10", "Finally, event odds."),
]


def run_demo(console: JarvisConsole) -> None:
    print(BANNER)
    print("◆ A short demonstration, sir.\n")
    for question, remark in DEMO_SCRIPT:
        print(f"› {question}")
        print(f"  {remark}")
        for line in console.ask(question).splitlines():
            print(f"  {line}")
        print()
    print("◆ Your turn. Type 'quit' when you've had enough, sir.\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='jarvis',
        description="Jarvis — a prediction-only AI (trading direction, forecasts, "
                    "sequences, event odds, risk). Runs on local statistics.",
    )
    parser.add_argument('question', nargs='*', help='one-shot prediction question')
    parser.add_argument('--json', action='store_true',
                        help='one-shot mode: emit raw JSON instead of prose')
    parser.add_argument('--demo', action='store_true', help='run a guided demo')
    parser.add_argument('--file', help='load a price series file before the question')
    args = parser.parse_args(argv)

    console = JarvisConsole()

    if args.demo:
        run_demo(console)
        return _repl(console)

    if args.file:
        print(console._load(f"load {args.file}"))

    if args.question:
        question = ' '.join(args.question)
        if args.json:
            nums = _numbers(question)
            if len(nums) >= 3:
                console.series = nums
                console.symbol = _symbol_from(question) or console.symbol
            low = question.lower()
            result: Dict[str, Any]
            if any(w in low for w in ('odds', 'probab', 'chance', 'likel')):
                m = re.search(r'(\d+)\s*(?:/|out of|of|in)\s*(\d+)', low)
                if m and 0 < int(m.group(2)) and int(m.group(1)) <= int(m.group(2)):
                    result = console.agent.event_probability(
                        successes=int(m.group(1)), trials=int(m.group(2)))
                else:
                    # base-rate phrasing or a request for guidance
                    result = {'reply': console._event(question)}
            elif any(w in low for w in ('scenario', 'bull', 'bear')):
                result = (console.agent.scenarios(console.series, symbol=console.symbol)
                          if console.series else {'error': 'no series'})
            elif 'risk' in low or 'volatil' in low:
                result = (console.agent.assess_risk(console.series, symbol=console.symbol)
                          if console.series else {'error': 'no series'})
            elif any(w in low for w in ('direction', 'up', 'down', 'trend', 'market',
                                        'trade', 'price')):
                result = (console.agent.predict_direction(console.series, symbol=console.symbol)
                          if console.series else {'error': 'no series'})
            else:
                result = console._json_default(question)
            print(json.dumps(result, indent=2, default=str))
            return 0
        print(console.ask(question))
        return 0

    return _repl(console)


def _repl(console: JarvisConsole) -> int:
    print(BANNER)
    while True:
        try:
            question = input("› ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye, sir. Do mind the volatility out there.")
            return 0
        if not question:
            continue
        reply = console.ask(question)
        for line in reply.splitlines():
            print(f"  {line}")
        print()
        if question.lower() in ('quit', 'exit'):
            return 0


if __name__ == '__main__':
    sys.exit(main())
