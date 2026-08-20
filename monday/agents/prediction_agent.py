"""
Prediction Agent ("Jarvis") - Forecasting & probability specialist

Jarvis answers exactly one class of question: *what happens next*.

Domains:
- Trading / markets  : direction probabilities (up / down / sideways), scenario
                       analysis, support & resistance, volatility and risk.
- Time series        : next-value forecasts with confidence intervals
                       (trend + Holt double exponential smoothing ensemble).
- Sequences          : "what is the next number" pattern solving
                       (arithmetic, geometric, polynomial, linear recurrence,
                       cycles).
- Events             : probability estimation from base rates, frequencies and
                       weighted evidence (log-odds updates).

Everything runs on plain Python (no external dependencies) so the agent works
anywhere the Monday platform runs. All market outputs carry an explicit
disclaimer: these are transparent statistical estimates, never financial
advice.
"""

from typing import Dict, List, Any, Optional, Tuple
import math
import re
import time

from ..core.base_agent import BaseAgent, AgentRequest, AgentResponse, AgentStatus
from ..core.agent_registry import AgentType, AgentCapability

# --------------------------------------------------------------------------
# Small statistics helpers (stdlib only)
# --------------------------------------------------------------------------


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _sma(values: List[float], window: int) -> List[Optional[float]]:
    """Simple moving average; None until the window fills."""
    out: List[Optional[float]] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
        else:
            out.append(_mean(values[i + 1 - window: i + 1]))
    return out


def _ema(values: List[float], span: int) -> List[float]:
    """Exponential moving average over the full series."""
    if not values:
        return []
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def _returns(values: List[float]) -> List[float]:
    """Fractional period-to-period returns."""
    return [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1] != 0
    ]


def _ols(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    """Ordinary least squares fit. Returns (slope, intercept, r_squared)."""
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0, 0.0
    mx, my = _mean(xs), _mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my, 0.0
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return slope, intercept, r2


def _percentile(sorted_values: List[float], p: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    f = math.floor(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _solve_linear_system(a: List[List[float]], b: List[float]) -> Optional[List[float]]:
    """Solve A x = b by Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _logistic(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------


class PredictionAgent(BaseAgent):
    """
    Specialist agent for prediction tasks ("Jarvis").

    Capabilities:
    - prediction:              general next-thing forecasting
    - forecasting:             time series next-value forecasts with CIs
    - market_analysis:         trading direction probabilities + indicators
    - trend_analysis:          momentum / trend strength assessment
    - probability_estimation:  event odds from base rates and evidence
    - sequence_prediction:     next number in a pattern
    - risk_assessment:         volatility, drawdown, VaR
    """

    NAME = "Jarvis"
    DISCLAIMER = (
        "Statistical estimate from transparent rule-based models on the data "
        "provided. Not financial advice; markets can and do defy any model."
    )

    def __init__(self):
        super().__init__("prediction")
        self._capabilities = [
            'prediction',
            'forecasting',
            'market_analysis',
            'trend_analysis',
            'probability_estimation',
            'sequence_prediction',
            'risk_assessment',
            'trading_analysis',
        ]
        self._model_requirements = ['reasoning', 'numeric']

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def execute(self, request: AgentRequest) -> AgentResponse:
        """Execute a prediction task."""
        start_time = time.time()
        self.status = AgentStatus.THINKING
        self.current_task_id = request.task_id

        try:
            validation_errors = self.validate_request(request)
            if validation_errors:
                return self._create_response(
                    task_id=request.task_id,
                    status=AgentStatus.FAILED,
                    errors=validation_errors,
                    execution_time=time.time() - start_time,
                )

            spec = request.inputs.get('specification', {}) or {}
            objective = (request.objective or '').lower()
            entities = spec.get('entities', {}) or {}
            series_pool = spec.get('series') or entities.get('series') \
                or _extract_series(objective)
            symbol = spec.get('symbol') or entities.get('symbol')

            mode = spec.get('mode') or self._detect_mode(objective, spec)

            if mode == 'sequence':
                result = self.predict_sequence(series_pool)
            elif mode == 'direction':
                result = self.predict_direction(series_pool, symbol=symbol)
            elif mode == 'risk':
                result = self.assess_risk(series_pool, symbol=symbol)
            elif mode == 'event':
                result = self.event_probability(
                    base_rate=spec.get('base_rate'),
                    successes=spec.get('successes'),
                    trials=spec.get('trials'),
                    evidence=spec.get('evidence'),
                )
            elif mode == 'market':
                result = self.analyze_market(series_pool, symbol=symbol)
            else:  # 'forecast' or auto
                series = series_pool
                if len(series) >= 3:
                    seq = self.predict_sequence(series)
                    if seq['pattern'] != 'none':
                        result = seq
                    else:
                        result = self.forecast_series(
                            series, horizon=int(spec.get('horizon', 1))
                        )
                else:
                    return self._create_response(
                        task_id=request.task_id,
                        status=AgentStatus.FAILED,
                        errors=[
                            "Need at least 3 data points to forecast. "
                            "Provide a series (e.g. 'prices: 101, 103, 99, 105') "
                            "or load a file in the Jarvis console."
                        ],
                        execution_time=time.time() - start_time,
                    )

            if result.get('error'):
                return self._create_response(
                    task_id=request.task_id,
                    status=AgentStatus.FAILED,
                    errors=[result['error']],
                    execution_time=time.time() - start_time,
                )

            self.status = AgentStatus.COMPLETED
            return self._create_response(
                task_id=request.task_id,
                status=AgentStatus.COMPLETED,
                output=result,
                artifacts=[{'type': f"prediction_{mode}", 'data': result}],
                confidence=float(result.get('confidence', 0.5)),
                recommended_next_action=result.get('next_action'),
                execution_time=time.time() - start_time,
                model_usage={'engine': 'jarvis-statistical-ensemble', 'external_models': 0},
            )

        except Exception as e:
            self.status = AgentStatus.FAILED
            return self._create_response(
                task_id=request.task_id,
                status=AgentStatus.FAILED,
                errors=[f"Prediction engine failure: {e}"],
                execution_time=time.time() - start_time,
            )

    def _detect_mode(self, objective: str, spec: Dict[str, Any]) -> str:
        """Infer the prediction mode from the objective text."""
        if spec.get('series') and not objective:
            return 'forecast'
        if re.search(r'next (number|term|value) (in|of|for)', objective) or \
                'sequence' in objective or 'pattern' in objective:
            return 'sequence'
        if any(w in objective for w in ('up', 'down', 'direction', 'bull', 'bear',
                                        'trend', 'market', 'trade', 'trading',
                                        'candle', 'rally', 'correction')):
            return 'direction'
        if any(w in objective for w in ('risk', 'volatil', 'drawdown', 'var ')):
            return 'risk'
        if any(w in objective for w in ('probab', 'odds', 'chance', 'likely', 'likelihood')):
            return 'event'
        return 'forecast'

    # ------------------------------------------------------------------
    # Technical indicators
    # ------------------------------------------------------------------

    def indicators(self, values: List[float]) -> Dict[str, Any]:
        """Compute standard technical indicators for a price series."""
        if len(values) < 5:
            return {'error': "Need at least 5 data points for indicators."}

        rets = _returns(values)
        last = values[-1]

        sma20 = _sma(values, min(20, len(values)))[-1]
        ema12 = _ema(values, 12)
        ema26 = _ema(values, 26)
        macd_line = [f - s for f, s in zip(ema12, ema26)]
        signal_line = _ema(macd_line, 9)
        macd_hist = macd_line[-1] - signal_line[-1]

        # RSI (Wilder smoothing)
        rsi = None
        if len(values) > 14:
            gains, losses = [], []
            for i in range(1, len(values)):
                ch = values[i] - values[i - 1]
                gains.append(max(ch, 0.0))
                losses.append(max(-ch, 0.0))
            avg_gain, avg_loss = _mean(gains[:14]), _mean(losses[:14])
            for i in range(14, len(gains)):
                avg_gain = (avg_gain * 13 + gains[i]) / 14
                avg_loss = (avg_loss * 13 + losses[i]) / 14
            rsi = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

        # Bollinger-style bands
        window = min(20, len(values))
        recent = values[-window:]
        bands_mid = _mean(recent)
        bands_sd = _stdev(recent)

        # Support / resistance from local extrema
        supports, resistances = self._support_resistance(values)
        nearest_support = max([s for s in supports if s < last], default=None)
        nearest_resistance = min([r for r in resistances if r > last], default=None)

        return {
            'last': last,
            'sma': sma20,
            'ema12': ema12[-1],
            'ema26': ema26[-1],
            'macd_histogram': macd_hist,
            'rsi': rsi,
            'bollinger': {
                'upper': bands_mid + 2 * bands_sd,
                'mid': bands_mid,
                'lower': bands_mid - 2 * bands_sd,
            },
            'support': nearest_support,
            'resistance': nearest_resistance,
            'volatility_per_period': _stdev(rets),
        }

    def _support_resistance(self, values: List[float], k: int = 2) -> Tuple[List[float], List[float]]:
        """Find local minima (support) and maxima (resistance) levels."""
        window = values[-min(len(values), 40):]
        supports: List[float] = []
        resistances: List[float] = []
        for i in range(k, len(window) - k):
            slice_ = window[i - k: i + k + 1]
            if window[i] == min(slice_) and window[i] not in supports:
                supports.append(window[i])
            if window[i] == max(slice_) and window[i] not in resistances:
                resistances.append(window[i])
        return supports, resistances

    # ------------------------------------------------------------------
    # 1) Trading direction prediction
    # ------------------------------------------------------------------

    def predict_direction(self, values: List[float], symbol: Optional[str] = None,
                          periods_ahead: int = 1) -> Dict[str, Any]:
        """
        Predict the direction of the NEXT move as probabilities.

        Combines six transparent signals (momentum, EMA crossover, trend
        slope, RSI extremes, mean reversion, MACD histogram) into a weighted
        score, then maps the score to calibrated-looking probabilities.
        """
        if len(values) < 6:
            return {'error': "Need at least 6 data points to judge direction."}

        rets = _returns(values)
        vol = _stdev(rets)
        last = values[-1]
        n_back = min(5, len(values) - 1)

        # --- signal 1: normalized momentum -----------------------------
        lookback = values[-(n_back + 1)]
        momentum_raw = (last - lookback) / abs(lookback) if lookback else 0.0
        denom = vol * math.sqrt(n_back) + 1e-9
        s_momentum = math.tanh(momentum_raw / denom)

        # --- signal 2: EMA crossover ------------------------------------
        ema_f, ema_s = _ema(values, 5), _ema(values, 15)
        spread = (ema_f[-1] - ema_s[-1])
        s_ema = math.tanh(spread / (vol * last + 1e-9) * 2)

        # --- signal 3: trend slope (OLS over recent window) -------------
        window = values[-min(len(values), 20):]
        slope, _, r2 = _ols(list(range(len(window))), [float(v) for v in window])
        s_trend = math.tanh(slope / (vol * last + 1e-9) / 2) * max(r2, 0.0)

        # --- signal 4: RSI extremes (contrarian at extremes) -------------
        ind = self.indicators(values)
        rsi = ind.get('rsi')
        s_rsi = 0.0
        if rsi is not None:
            if rsi >= 70:
                s_rsi = -min((rsi - 70) / 20.0, 1.0)
            elif rsi <= 30:
                s_rsi = min((30 - rsi) / 20.0, 1.0)

        # --- signal 5: mean reversion (distance from SMA) ----------------
        sma_val = ind['sma'] or last
        sd_window = _stdev(values[-min(len(values), 20):]) + 1e-9
        z = (last - sma_val) / sd_window
        s_meanrev = -math.tanh(z / 2.0)

        # --- signal 6: MACD histogram ------------------------------------
        s_macd = math.tanh(ind['macd_histogram'] / (vol * last + 1e-9) * 2)

        signals = [
            {'name': 'momentum', 'value': s_momentum, 'weight': 0.25},
            {'name': 'ema_crossover', 'value': s_ema, 'weight': 0.20},
            {'name': 'trend_slope', 'value': s_trend, 'weight': 0.20},
            {'name': 'rsi_extreme', 'value': s_rsi, 'weight': 0.10},
            {'name': 'mean_reversion', 'value': s_meanrev, 'weight': 0.15},
            {'name': 'macd_histogram', 'value': s_macd, 'weight': 0.10},
        ]

        net = sum(s['value'] * s['weight'] for s in signals)
        net = _clamp(net, -1.0, 1.0)
        weighted_abs = sum(abs(s['value']) * s['weight'] for s in signals) + 1e-9
        agreement = abs(net) / weighted_abs  # 0 = chaos, 1 = unanimous

        # Map score to probabilities
        p_up_directional = _logistic(3.2 * net)
        sideways = _clamp(0.35 * (1.0 - abs(net)), 0.05, 0.35)
        p_up = (1.0 - sideways) * p_up_directional
        p_down = (1.0 - sideways) * (1.0 - p_up_directional)

        # Confidence: signal strength + agreement, tempered by data length
        data_factor = min(len(values) / 30.0, 1.0)
        confidence = _clamp(0.45 * abs(net) + 0.45 * agreement + 0.10 * data_factor,
                            0.05, 0.90)

        expected_move = net * vol * last * math.sqrt(periods_ahead)
        verdict = 'UP' if p_up > max(p_down, sideways) else (
            'DOWN' if p_down > max(p_up, sideways) else 'SIDEWAYS')

        return {
            'kind': 'direction',
            'symbol': symbol or 'series',
            'last_value': last,
            'probabilities': {
                'up': round(p_up, 3),
                'down': round(p_down, 3),
                'sideways': round(sideways, 3),
            },
            'verdict': verdict,
            'expected_move_pct': round(expected_move / last * 100, 3) if last else 0.0,
            'confidence': round(confidence, 3),
            'signals': [
                {'name': s['name'], 'value': round(s['value'], 3),
                 'weight': s['weight'], 'reading': 'bullish' if s['value'] > 0.15
                 else ('bearish' if s['value'] < -0.15 else 'neutral')}
                for s in signals
            ],
            'net_score': round(net, 3),
            'signal_agreement': round(agreement, 3),
            'support': ind.get('support'),
            'resistance': ind.get('resistance'),
            'volatility_per_period': round(vol, 5),
            'data_points': len(values),
            'disclaimer': self.DISCLAIMER,
            'next_action': 'Run scenarios or risk assessment for position sizing context',
        }

    # ------------------------------------------------------------------
    # 2) Scenario analysis
    # ------------------------------------------------------------------

    def scenarios(self, values: List[float], symbol: Optional[str] = None) -> Dict[str, Any]:
        """Bull / base / bear scenario ranges for the next period."""
        if len(values) < 6:
            return {'error': "Need at least 6 data points for scenarios."}

        direction = self.predict_direction(values, symbol=symbol)
        if 'error' in direction:
            return direction

        last = values[-1]
        vol = _stdev(_returns(values))
        drift = direction['net_score'] * vol

        bull = last * (1 + max(drift * 1.6, vol * 0.8))
        base = last * (1 + drift)
        bear = last * (1 + min(drift * 1.6, -vol * 0.8))

        p = direction['probabilities']
        bull_p = round(p['up'] * 0.75, 3)
        bear_p = round(p['down'] * 0.75, 3)
        base_p = round(max(1.0 - bull_p - bear_p, 0.0), 3)

        return {
            'kind': 'scenarios',
            'symbol': symbol or 'series',
            'last_value': last,
            'scenarios': [
                {'name': 'bull', 'target': round(bull, 4),
                 'change_pct': round((bull / last - 1) * 100, 2), 'probability': bull_p},
                {'name': 'base', 'target': round(base, 4),
                 'change_pct': round((base / last - 1) * 100, 2), 'probability': base_p},
                {'name': 'bear', 'target': round(bear, 4),
                 'change_pct': round((bear / last - 1) * 100, 2), 'probability': bear_p},
            ],
            'confidence': direction['confidence'],
            'disclaimer': self.DISCLAIMER,
        }

    # ------------------------------------------------------------------
    # 3) Next-value time series forecast
    # ------------------------------------------------------------------

    def forecast_series(self, values: List[float], horizon: int = 1) -> Dict[str, Any]:
        """
        Forecast the next value(s) of a numeric series.

        Ensemble of three engines, weighted by walk-forward backtest error:
        - OLS linear trend (responsive window)
        - Holt double exponential smoothing (level + trend)
        - SMA continuation (short-term inertia)
        """
        if len(values) < 3:
            return {'error': "Need at least 3 data points to forecast."}
        horizon = max(1, min(int(horizon), 10))

        xs = [float(i) for i in range(len(values))]
        ys = [float(v) for v in values]

        def _linear_next(series: List[float], steps: int = 1) -> float:
            window = series[-min(len(series), 12):]
            wx = [float(i) for i in range(len(window))]
            slope, intercept, _ = _ols(wx, window)
            return slope * (len(window) - 1 + steps) + intercept

        def _holt_next(series: List[float], steps: int = 1,
                       alpha: float = 0.5, beta: float = 0.25) -> float:
            level, trend = series[0], series[1] - series[0]
            for v in series[1:]:
                prev_level = level
                level = alpha * v + (1 - alpha) * (level + trend)
                trend = beta * (level - prev_level) + (1 - beta) * trend
            return level + steps * trend

        def _sma_next(series: List[float], steps: int = 1) -> float:
            window = series[-min(len(series), 3):]
            prev = series[-min(len(series), 3) - 1] if len(series) > 3 else window[0]
            delta = _mean(window) - prev
            return series[-1] + steps * delta

        engines = {
            'linear_trend': _linear_next,
            'holt_smoothing': _holt_next,
            'sma_continuation': _sma_next,
        }

        # Walk-forward backtest over the tail of the series
        backtest_len = min(len(ys) - 3, 8)
        errors: Dict[str, List[float]] = {name: [] for name in engines}
        if backtest_len >= 1:
            for cut in range(len(ys) - backtest_len, len(ys)):
                actual = ys[cut]
                history = ys[:cut]
                for name, fn in engines.items():
                    try:
                        errors[name].append(abs(fn(history) - actual))
                    except Exception:
                        errors[name].append(abs(ys[cut - 1] - actual))

        weights: Dict[str, float] = {}
        for name in engines:
            mae = _mean(errors[name]) if errors[name] else 1.0
            weights[name] = 1.0 / (mae + 1e-9)
        total_w = sum(weights.values())
        weights = {k: v / total_w for k, v in weights.items()}

        # Ensemble multi-step forecast
        path: List[float] = []
        extended = ys[:]
        for _ in range(horizon):
            value = sum(w * fn(extended, 1) for name, w, fn in
                        [(n, weights[n], f) for n, f in engines.items()])
            path.append(value)
            extended.append(value)

        # Confidence interval from backtest residuals of the ensemble
        if backtest_len >= 1:
            combined = []
            for cut in range(len(ys) - backtest_len, len(ys)):
                history = ys[:cut]
                pred = sum(weights[n] * f(history) for n, f in engines.items())
                combined.append(abs(pred - ys[cut]))
            residual_sd = _stdev(combined) or _mean(combined) or 0.0
        else:
            residual_sd = _stdev(ys) * 0.25

        step_scale = math.sqrt(horizon)
        slope, _, r2 = _ols(xs, ys)
        trend_word = ('rising' if slope > 0 else 'falling' if slope < 0 else 'flat')

        point = path[-1]
        result = {
            'kind': 'forecast',
            'history_points': len(values),
            'last_value': ys[-1],
            'horizon': horizon,
            'next_value': round(point, 4),
            'path': [round(v, 4) for v in path],
            'interval_80': [
                round(point - 1.2816 * residual_sd * step_scale, 4),
                round(point + 1.2816 * residual_sd * step_scale, 4),
            ],
            'interval_95': [
                round(point - 1.96 * residual_sd * step_scale, 4),
                round(point + 1.96 * residual_sd * step_scale, 4),
            ],
            'trend': trend_word,
            'trend_r2': round(r2, 3),
            'engine_weights': {k: round(v, 3) for k, v in weights.items()},
            'confidence': round(_clamp(0.35 + 0.5 * max(r2, 0.0) - 0.1 * (residual_sd / (abs(ys[-1]) + 1e-9)), 0.10, 0.90), 3),
            'next_action': 'Longer history improves calibration; feed more points if available',
        }
        if trend_word != 'flat' and abs(slope) > 0:
            result['disclaimer'] = self.DISCLAIMER
        return result

    # ------------------------------------------------------------------
    # 4) Sequence pattern solving ("next number in ...")
    # ------------------------------------------------------------------

    def predict_sequence(self, values: List[float]) -> Dict[str, Any]:
        """Identify an exact pattern in a sequence and extend it."""
        if len(values) < 3:
            return {'error': "Need at least 3 terms to detect a pattern."}

        seq = [float(v) for v in values]
        n = len(seq)

        def result(pattern: str, nxt: float, detail: str,
                   confidence: float) -> Dict[str, Any]:
            return {
                'kind': 'sequence',
                'pattern': pattern,
                'next_value': round(nxt, 6),
                'detail': detail,
                'confidence': confidence,
                'sequence': seq,
                'next_action': 'Verify the pattern matches your intent before relying on it',
            }

        # constant
        if all(v == seq[0] for v in seq):
            return result('constant', seq[0], 'Every term is identical.', 0.99)

        # arithmetic: constant first differences
        diffs = [seq[i + 1] - seq[i] for i in range(n - 1)]
        if all(abs(d - diffs[0]) <= 1e-9 * max(1.0, abs(diffs[0])) for d in diffs):
            return result('arithmetic', seq[-1] + diffs[0],
                          f'Common difference {diffs[0]:g}.', 0.99)

        # geometric: constant ratio
        if all(abs(v) > 1e-12 for v in seq):
            ratios = [seq[i + 1] / seq[i] for i in range(n - 1)]
            if all(abs(r - ratios[0]) <= 1e-9 * max(1.0, abs(ratios[0])) for r in ratios):
                return result('geometric', seq[-1] * ratios[0],
                              f'Common ratio {ratios[0]:g}.', 0.99)

        # polynomial: constant k-th differences (quadratic / cubic)
        rows: List[List[float]] = [seq[:], diffs[:]]
        for order in (2, 3):
            # descend one level in the difference table
            prev_row = rows[-1]
            if len(prev_row) < 2:
                break
            rows.append([prev_row[i + 1] - prev_row[i] for i in range(len(prev_row) - 1)])
            deepest = rows[-1]
            if len(deepest) >= 2 and all(
                    abs(d - deepest[0]) <= 1e-9 * max(1.0, abs(deepest[0])) for d in deepest):
                # extend the difference pyramid bottom-up to get the next term
                add = deepest[-1]
                for r in range(len(rows) - 2, -1, -1):
                    add = rows[r][-1] + add
                    rows[r].append(add)
                return result(f'polynomial_order_{order}', rows[0][-1],
                              f'Constant order-{order} differences '
                              f'(degree-{order} polynomial).', 0.95)

        # repeating cycle (checked before recurrence: the simpler
        # explanation wins; requires the cycle to appear at least twice)
        for k in range(1, n // 2 + 1):
            cycle = seq[:k]
            if all(seq[i] == cycle[i % k] for i in range(n)):
                return result('cyclic', cycle[n % k],
                              f'Repeating cycle of length {k}.', 0.98)

        # linear recurrence of order 2 or 3: v[n] = sum(c_i * v[n-1-i]) + c_last
        for order in (2, 3):
            if n >= 2 * order + 2:
                a = [[seq[i - j] for j in range(1, order + 1)] + [1.0]
                     for i in range(order, 2 * order + 1)]
                b = [seq[i] for i in range(order, 2 * order + 1)]
                coeffs = _solve_linear_system(a, b)
                if coeffs:
                    tol = 1e-6 * max(1.0, max(abs(v) for v in seq))
                    ok = True
                    for i in range(order, n):
                        pred = sum(coeffs[j] * seq[i - 1 - j] for j in range(order)) + coeffs[-1]
                        if abs(pred - seq[i]) > tol:
                            ok = False
                            break
                    if ok:
                        nxt = sum(coeffs[j] * seq[n - 1 - j] for j in range(order)) + coeffs[-1]
                        terms = ' + '.join(
                            f'{coeffs[j]:.4g}·v[n-{j + 1}]' for j in range(order)
                        ) + f' + {coeffs[-1]:.4g}'
                        name = 'fibonacci_like' if (order == 2 and abs(coeffs[0] - 1) < 1e-6
                                                    and abs(coeffs[1] - 1) < 1e-6
                                                    and abs(coeffs[2]) < 1e-6) \
                            else f'linear_recurrence_order_{order}'
                        return result(name, nxt, f'v[n] = {terms}', 0.97)


        # no exact pattern: fall back to statistical forecast, honestly labelled
        fallback = self.forecast_series(seq)
        if 'error' in fallback:
            return fallback
        fallback.update({
            'pattern': 'none',
            'detail': 'No exact rule detected; values come from a statistical forecast.',
            'confidence': min(fallback.get('confidence', 0.4), 0.55),
        })
        return fallback

    # ------------------------------------------------------------------
    # 5) Event probability
    # ------------------------------------------------------------------

    def event_probability(
        self,
        base_rate: Optional[float] = None,
        successes: Optional[int] = None,
        trials: Optional[int] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Estimate the probability that an event happens.

        Two modes:
        - Frequency: k successes in n trials -> Beta(1,1) posterior
          (Laplace) mean and 95% credible interval.
        - Base rate + evidence: each piece of evidence shifts the log-odds,
          with strong evidence worth up to a 4x odds multiplier.
        """
        steps: List[str] = []

        if successes is not None and trials is not None:
            if trials <= 0 or successes < 0 or successes > trials:
                return {'error': "Need 0 <= successes <= trials and trials >= 1."}
            k, n = successes, trials
            mean = (k + 1) / (n + 2)
            sd = math.sqrt(mean * (1 - mean) / (n + 3))
            steps.append(f'Observed {k} successes in {n} trials '
                         f'(Laplace-smoothed Beta posterior).')
            return {
                'kind': 'event_probability',
                'mode': 'frequency',
                'probability': round(mean, 4),
                'interval_95': [round(max(0.0, mean - 1.96 * sd), 4),
                                round(min(1.0, mean + 1.96 * sd), 4)],
                'reasoning': steps,
                'confidence': round(_clamp(0.3 + n / 50.0, 0.3, 0.9), 3),
                'next_action': 'More trials narrow the interval',
            }

        if base_rate is None:
            base_rate = 0.5
            steps.append('No base rate supplied; assuming an uninformative 50%.')
        if not 0.0 < base_rate < 1.0:
            return {'error': "Base rate must be strictly between 0 and 1."}

        p = base_rate
        steps.append(f'Starting from base rate {base_rate:.1%}.')

        if evidence:
            odds = p / (1.0 - p)
            for ev in evidence:
                direction = str(ev.get('direction', 'for')).lower()
                strength = _clamp(float(ev.get('strength', 0.5)), 0.0, 1.0)
                factor = math.exp(strength * math.log(4.0))  # up to 4x odds
                if direction in ('against', 'contra', 'negative', 'no'):
                    odds /= factor
                    steps.append(f'Evidence AGAINST (strength {strength:.2f}): '
                                 f'odds ÷ {factor:.2f}.')
                else:
                    odds *= factor
                    steps.append(f'Evidence FOR (strength {strength:.2f}): '
                                 f'odds × {factor:.2f}.')
            p = odds / (1.0 + odds)

        p = _clamp(p, 0.01, 0.99)
        return {
            'kind': 'event_probability',
            'mode': 'base_rate_evidence',
            'probability': round(p, 4),
            'probability_pct': round(p * 100, 1),
            'reasoning': steps,
            'confidence': 0.5 if not evidence else 0.6,
            'next_action': 'Supply a base rate or history for a sharper estimate',
        }

    # ------------------------------------------------------------------
    # 6) Risk assessment
    # ------------------------------------------------------------------

    def assess_risk(self, values: List[float],
                    symbol: Optional[str] = None) -> Dict[str, Any]:
        """Volatility, drawdown, historical VaR and trend stability."""
        if len(values) < 5:
            return {'error': "Need at least 5 data points for risk metrics."}

        rets = _returns(values)
        vol = _stdev(rets)
        annualized = vol * math.sqrt(252)  # assumes daily bars

        # max drawdown
        peak = values[0]
        max_dd = 0.0
        for v in values:
            peak = max(peak, v)
            if peak > 0:
                max_dd = min(max_dd, (v - peak) / peak)

        sorted_rets = sorted(rets)
        var95 = _percentile(sorted_rets, 0.05)

        # volatility regime: recent vs full
        recent = _stdev(rets[-5:]) if len(rets) >= 5 else vol
        regime = ('expanding' if vol > 0 and recent > vol * 1.25
                  else 'contracting' if vol > 0 and recent < vol * 0.75
                  else 'stable')

        xs = [float(i) for i in range(len(values))]
        _, _, r2 = _ols(xs, [float(v) for v in values])

        score = _clamp(
            (min(vol / 0.03, 1.0) * 4.0
             + min(abs(max_dd) / 0.20, 1.0) * 3.0
             + (1.0 - max(r2, 0.0)) * 2.0
             + (0.5 if regime == 'expanding' else 0.0)),
            0.0, 10.0)
        label = ('low' if score < 3 else 'medium' if score < 5.5
                 else 'high' if score < 8 else 'extreme')

        result = {
            'kind': 'risk',
            'symbol': symbol or 'series',
            'volatility_per_period': round(vol, 5),
            'annualized_volatility_pct': round(annualized * 100, 2),
            'max_drawdown_pct': round(max_dd * 100, 2),
            'historical_var_95_pct': round(var95 * 100, 2),
            'volatility_regime': regime,
            'trend_stability_r2': round(r2, 3),
            'risk_score': round(score, 2),
            'risk_label': label,
            'data_points': len(values),
            'disclaimer': self.DISCLAIMER,
        }
        if len(values) < 20:
            result['warnings'] = [
                f'Only {len(values)} data points; estimates are coarse. '
                f'20+ is recommended.'
            ]
        return result

    # ------------------------------------------------------------------
    # 7) Full market brief (direction + scenarios + risk + indicators)
    # ------------------------------------------------------------------

    def analyze_market(self, values: List[float],
                       symbol: Optional[str] = None) -> Dict[str, Any]:
        """One-shot market brief: direction, scenarios, risk and indicators."""
        direction = self.predict_direction(values, symbol=symbol)
        if 'error' in direction:
            return direction
        return {
            'kind': 'market_brief',
            'symbol': symbol or 'series',
            'direction': direction,
            'scenarios': self.scenarios(values, symbol=symbol)['scenarios'],
            'risk': self.assess_risk(values, symbol=symbol),
            'indicators': {
                'rsi': direction['signals'] and self.indicators(values).get('rsi'),
                'support': direction.get('support'),
                'resistance': direction.get('resistance'),
            },
            'confidence': direction['confidence'],
            'disclaimer': self.DISCLAIMER,
            'next_action': 'Re-run after each new bar; probabilities decay quickly',
        }


# --------------------------------------------------------------------------
# Helpers shared with the console / analyzer
# --------------------------------------------------------------------------

_NUMBER_RE = re.compile(r'-?\d+(?:\.\d+)?')


def _extract_series(text: str) -> List[float]:
    """Extract a numeric series (>= 3 numbers) from free text, else []."""
    if not text:
        return []
    numbers = [float(m) for m in _NUMBER_RE.findall(text)]
    return numbers if len(numbers) >= 3 else []


def build_default_capabilities() -> List[AgentCapability]:
    """Capability descriptors used when registering Jarvis with the registry."""
    return [
        AgentCapability('prediction', 'General next-thing forecasting'),
        AgentCapability('forecasting', 'Time series next-value forecasts with intervals'),
        AgentCapability('market_analysis', 'Trading direction probabilities and indicators'),
        AgentCapability('trend_analysis', 'Momentum and trend strength assessment'),
        AgentCapability('probability_estimation', 'Event odds from base rates and evidence'),
        AgentCapability('sequence_prediction', 'Next term of a numeric pattern'),
        AgentCapability('risk_assessment', 'Volatility, drawdown and VaR metrics'),
    ]
