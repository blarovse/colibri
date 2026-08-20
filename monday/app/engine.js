/*
 * Jarvis prediction engine — JavaScript port of monday/agents/prediction_agent.py
 * Pure functions, no dependencies. Attaches window.JarvisEngine (or module.exports).
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory();
  else root.JarvisEngine = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DISCLAIMER =
    'Statistical estimate from transparent rule-based models on the data provided. ' +
    'Not financial advice; markets can and do defy any model.';

  // ---------------------------------------------------------------- math
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
  const logistic = (x) => 1 / (1 + Math.exp(-x));
  const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
  function stdev(xs) {
    if (xs.length < 2) return 0;
    const m = mean(xs);
    return Math.sqrt(xs.reduce((a, b) => a + (b - m) * (b - m), 0) / (xs.length - 1));
  }
  function sma(values, window) {
    return values.map((_, i) =>
      i + 1 < window ? null : mean(values.slice(i + 1 - window, i + 1))
    );
  }
  function ema(values, span) {
    if (!values.length) return [];
    const alpha = 2 / (span + 1);
    const out = [values[0]];
    for (let i = 1; i < values.length; i++) out.push(alpha * values[i] + (1 - alpha) * out[i - 1]);
    return out;
  }
  function returns(values) {
    const out = [];
    for (let i = 1; i < values.length; i++) if (values[i - 1] !== 0) out.push((values[i] - values[i - 1]) / values[i - 1]);
    return out;
  }
  function ols(xs, ys) {
    const n = xs.length;
    if (n < 2) return { slope: 0, intercept: ys[0] || 0, r2: 0 };
    const mx = mean(xs), my = mean(ys);
    let sxx = 0, sxy = 0;
    for (let i = 0; i < n; i++) { sxx += (xs[i] - mx) ** 2; sxy += (xs[i] - mx) * (ys[i] - my); }
    if (sxx === 0) return { slope: 0, intercept: my, r2: 0 };
    const slope = sxy / sxx, intercept = my - slope * mx;
    let ssTot = 0, ssRes = 0;
    for (let i = 0; i < n; i++) {
      ssTot += (ys[i] - my) ** 2;
      ssRes += (ys[i] - (slope * xs[i] + intercept)) ** 2;
    }
    const r2 = ssTot > 0 ? 1 - ssRes / ssTot : 0;
    return { slope, intercept, r2 };
  }
  function percentile(sorted, p) {
    if (!sorted.length) return 0;
    if (sorted.length === 1) return sorted[0];
    const k = (sorted.length - 1) * p, f = Math.floor(k), c = Math.min(f + 1, sorted.length - 1);
    return f === c ? sorted[k] : sorted[f] + (sorted[c] - sorted[f]) * (k - f);
  }
  function solveLinearSystem(a, b) {
    const n = b.length;
    const m = a.map((row, i) => row.slice().concat([b[i]]));
    for (let col = 0; col < n; col++) {
      let pivot = col;
      for (let r = col + 1; r < n; r++) if (Math.abs(m[r][col]) > Math.abs(m[pivot][col])) pivot = r;
      if (Math.abs(m[pivot][col]) < 1e-12) return null;
      [m[col], m[pivot]] = [m[pivot], m[col]];
      for (let r = col + 1; r < n; r++) {
        const f = m[r][col] / m[col][col];
        for (let c = col; c <= n; c++) m[r][c] -= f * m[col][c];
      }
    }
    const x = new Array(n).fill(0);
    for (let r = n - 1; r >= 0; r--) {
      let s = 0;
      for (let c = r + 1; c < n; c++) s += m[r][c] * x[c];
      x[r] = (m[r][n] - s) / m[r][r];
    }
    return x;
  }
  const r3 = (x) => Math.round(x * 1000) / 1000;

  // ---------------------------------------------------------------- indicators
  function supportResistance(values, k = 2) {
    const window = values.slice(-Math.min(values.length, 40));
    const sup = [], res = [];
    for (let i = k; i < window.length - k; i++) {
      const slice = window.slice(i - k, i + k + 1);
      if (window[i] === Math.min(...slice) && !sup.includes(window[i])) sup.push(window[i]);
      if (window[i] === Math.max(...slice) && !res.includes(window[i])) res.push(window[i]);
    }
    return { supports: sup, resistances: res };
  }

  function indicators(values) {
    if (values.length < 5) return { error: 'Need at least 5 data points for indicators.' };
    const rets = returns(values), last = values[values.length - 1];
    const smaV = sma(values, Math.min(20, values.length)).pop();
    const ema12 = ema(values, 12), ema26 = ema(values, 26);
    const macdLine = ema12.map((f, i) => f - ema26[i]);
    const signalLine = ema(macdLine, 9);
    const macdHist = macdLine[macdLine.length - 1] - signalLine[signalLine.length - 1];

    let rsi = null;
    if (values.length > 14) {
      const gains = [], losses = [];
      for (let i = 1; i < values.length; i++) {
        const ch = values[i] - values[i - 1];
        gains.push(Math.max(ch, 0)); losses.push(Math.max(-ch, 0));
      }
      let ag = mean(gains.slice(0, 14)), al = mean(losses.slice(0, 14));
      for (let i = 14; i < gains.length; i++) { ag = (ag * 13 + gains[i]) / 14; al = (al * 13 + losses[i]) / 14; }
      rsi = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
    }
    const win = Math.min(20, values.length), recent = values.slice(-win);
    const mid = mean(recent), sd = stdev(recent);
    const { supports, resistances } = supportResistance(values);
    return {
      last, sma: smaV, macdHistogram: macdHist, rsi,
      bollinger: { upper: mid + 2 * sd, mid, lower: mid - 2 * sd },
      support: supports.filter((s) => s < last).length ? Math.max(...supports.filter((s) => s < last)) : null,
      resistance: resistances.filter((x) => x > last).length ? Math.min(...resistances.filter((x) => x > last)) : null,
      volatilityPerPeriod: stdev(rets),
    };
  }

  // ---------------------------------------------------------------- direction
  function predictDirection(values, symbol = null, periodsAhead = 1) {
    if (values.length < 6) return { error: 'Need at least 6 data points to judge direction.' };
    const rets = returns(values), vol = stdev(rets), last = values[values.length - 1];
    const nBack = Math.min(5, values.length - 1);
    const lookback = values[values.length - 1 - nBack];
    const momentumRaw = lookback ? (last - lookback) / Math.abs(lookback) : 0;
    const sMomentum = Math.tanh(momentumRaw / (vol * Math.sqrt(nBack) + 1e-9));
    const emaF = ema(values, 5), emaS = ema(values, 15);
    const sEma = Math.tanh(((emaF[emaF.length - 1] - emaS[emaS.length - 1]) / (vol * last + 1e-9)) * 2);
    const win = values.slice(-Math.min(values.length, 20)).map(Number);
    const { slope, r2 } = ols(win.map((_, i) => i), win);
    const sTrend = Math.tanh(slope / (vol * last + 1e-9) / 2) * Math.max(r2, 0);
    const ind = indicators(values);
    let sRsi = 0;
    if (ind.rsi != null) {
      if (ind.rsi >= 70) sRsi = -Math.min((ind.rsi - 70) / 20, 1);
      else if (ind.rsi <= 30) sRsi = Math.min((30 - ind.rsi) / 20, 1);
    }
    const smaVal = ind.sma != null ? ind.sma : last;
    const sdWin = stdev(values.slice(-Math.min(values.length, 20))) + 1e-9;
    const z = (last - smaVal) / sdWin;
    const sMeanrev = -Math.tanh(z / 2);
    const sMacd = Math.tanh((ind.macdHistogram / (vol * last + 1e-9)) * 2);

    const signals = [
      { name: 'momentum', value: sMomentum, weight: 0.25 },
      { name: 'ema_crossover', value: sEma, weight: 0.2 },
      { name: 'trend_slope', value: sTrend, weight: 0.2 },
      { name: 'rsi_extreme', value: sRsi, weight: 0.1 },
      { name: 'mean_reversion', value: sMeanrev, weight: 0.15 },
      { name: 'macd_histogram', value: sMacd, weight: 0.1 },
    ];
    let net = clamp(signals.reduce((a, s) => a + s.value * s.weight, 0), -1, 1);
    const weightedAbs = signals.reduce((a, s) => a + Math.abs(s.value) * s.weight, 0) + 1e-9;
    const agreement = Math.abs(net) / weightedAbs;

    const pUpDir = logistic(3.2 * net);
    const sideways = clamp(0.35 * (1 - Math.abs(net)), 0.05, 0.35);
    const pUp = (1 - sideways) * pUpDir, pDown = (1 - sideways) * (1 - pUpDir);
    const dataFactor = Math.min(values.length / 30, 1);
    const confidence = clamp(0.45 * Math.abs(net) + 0.45 * agreement + 0.1 * dataFactor, 0.05, 0.9);
    const expectedMove = net * vol * last * Math.sqrt(periodsAhead);
    const verdict = pUp > Math.max(pDown, sideways) ? 'UP'
      : pDown > Math.max(pUp, sideways) ? 'DOWN' : 'SIDEWAYS';

    return {
      kind: 'direction', symbol: symbol || 'series', lastValue: last,
      probabilities: { up: r3(pUp), down: r3(pDown), sideways: r3(sideways) },
      verdict, expectedMovePct: last ? r3((expectedMove / last) * 100) : 0,
      confidence: r3(confidence),
      signals: signals.map((s) => ({
        name: s.name, value: r3(s.value), weight: s.weight,
        reading: s.value > 0.15 ? 'bullish' : s.value < -0.15 ? 'bearish' : 'neutral',
      })),
      netScore: r3(net), signalAgreement: r3(agreement),
      support: ind.support, resistance: ind.resistance,
      volatilityPerPeriod: Math.round(vol * 100000) / 100000,
      dataPoints: values.length, disclaimer: DISCLAIMER,
    };
  }

  function scenarios(values, symbol = null) {
    if (values.length < 6) return { error: 'Need at least 6 data points for scenarios.' };
    const d = predictDirection(values, symbol);
    if (d.error) return d;
    const last = values[values.length - 1], vol = stdev(returns(values));
    const drift = d.netScore * vol;
    const bull = last * (1 + Math.max(drift * 1.6, vol * 0.8));
    const base = last * (1 + drift);
    const bear = last * (1 + Math.min(drift * 1.6, -vol * 0.8));
    const bp = r3(d.probabilities.up * 0.75), ep = r3(d.probabilities.down * 0.75);
    return {
      kind: 'scenarios', symbol: symbol || 'series', lastValue: last, confidence: d.confidence,
      disclaimer: DISCLAIMER,
      scenarios: [
        { name: 'bull', target: Math.round(bull * 10000) / 10000, changePct: Math.round((bull / last - 1) * 10000) / 100, probability: bp },
        { name: 'base', target: Math.round(base * 10000) / 10000, changePct: Math.round((base / last - 1) * 10000) / 100, probability: r3(Math.max(1 - bp - ep, 0)) },
        { name: 'bear', target: Math.round(bear * 10000) / 10000, changePct: Math.round((bear / last - 1) * 10000) / 100, probability: ep },
      ],
    };
  }

  // ---------------------------------------------------------------- forecast
  function forecastSeries(values, horizon = 1) {
    if (values.length < 3) return { error: 'Need at least 3 data points to forecast.' };
    horizon = Math.max(1, Math.min(Math.round(horizon), 10));
    const ys = values.map(Number);

    const linearNext = (series) => {
      const window = series.slice(-Math.min(series.length, 12));
      const { slope, intercept } = ols(window.map((_, i) => i), window);
      return slope * (window.length - 1 + 1) + intercept;
    };
    const holtNext = (series, steps = 1, alpha = 0.5, beta = 0.25) => {
      let level = series[0], trend = series[1] - series[0];
      for (let i = 1; i < series.length; i++) {
        const prev = level;
        level = alpha * series[i] + (1 - alpha) * (level + trend);
        trend = beta * (level - prev) + (1 - beta) * trend;
      }
      return level + steps * trend;
    };
    const smaNext = (series) => {
      const window = series.slice(-Math.min(series.length, 3));
      const prev = series.length > 3 ? series[series.length - 4] : window[0];
      return series[series.length - 1] + (mean(window) - prev);
    };
    const engines = { linear_trend: linearNext, holt_smoothing: (s) => holtNext(s, 1), sma_continuation: smaNext };

    const backLen = Math.min(ys.length - 3, 8);
    const errs = {};
    Object.keys(engines).forEach((n) => (errs[n] = []));
    if (backLen >= 1) {
      for (let cut = ys.length - backLen; cut < ys.length; cut++) {
        Object.keys(engines).forEach((name) => {
          try { errs[name].push(Math.abs(engines[name](ys.slice(0, cut)) - ys[cut])); }
          catch (e) { errs[name].push(Math.abs(ys[cut - 1] - ys[cut])); }
        });
      }
    }
    let weights = {};
    Object.keys(engines).forEach((n) => (weights[n] = 1 / (mean(errs[n].length ? errs[n] : [1]) + 1e-9)));
    const tw = Object.values(weights).reduce((a, b) => a + b, 0);
    Object.keys(weights).forEach((n) => (weights[n] /= tw));

    const path = [], extended = ys.slice();
    for (let s = 0; s < horizon; s++) {
      let v = 0;
      Object.keys(engines).forEach((n) => (v += weights[n] * engines[n](extended)));
      path.push(v); extended.push(v);
    }
    let residualSd;
    if (backLen >= 1) {
      const combined = [];
      for (let cut = ys.length - backLen; cut < ys.length; cut++) {
        let p = 0;
        Object.keys(engines).forEach((n) => (p += weights[n] * engines[n](ys.slice(0, cut))));
        combined.push(Math.abs(p - ys[cut]));
      }
      residualSd = stdev(combined) || mean(combined) || 0;
    } else residualSd = stdev(ys) * 0.25;

    const stepScale = Math.sqrt(horizon);
    const xs = ys.map((_, i) => i);
    const { slope, r2 } = ols(xs, ys);
    const trendWord = slope > 0 ? 'rising' : slope < 0 ? 'falling' : 'flat';
    const point = path[path.length - 1];
    const result = {
      kind: 'forecast', historyPoints: ys.length, lastValue: ys[ys.length - 1], horizon,
      nextValue: Math.round(point * 10000) / 10000,
      path: path.map((v) => Math.round(v * 10000) / 10000),
      interval80: [
        Math.round((point - 1.2816 * residualSd * stepScale) * 10000) / 10000,
        Math.round((point + 1.2816 * residualSd * stepScale) * 10000) / 10000,
      ],
      interval95: [
        Math.round((point - 1.96 * residualSd * stepScale) * 10000) / 10000,
        Math.round((point + 1.96 * residualSd * stepScale) * 10000) / 10000,
      ],
      trend: trendWord, trendR2: r3(r2),
      engineWeights: Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, r3(v)])),
      confidence: r3(clamp(0.35 + 0.5 * Math.max(r2, 0) - 0.1 * (residualSd / (Math.abs(ys[ys.length - 1]) + 1e-9)), 0.1, 0.9)),
    };
    if (trendWord !== 'flat' && slope !== 0) result.disclaimer = DISCLAIMER;
    return result;
  }

  // ---------------------------------------------------------------- sequences
  function predictSequence(values) {
    if (values.length < 3) return { error: 'Need at least 3 terms to detect a pattern.' };
    const seq = values.map(Number), n = seq.length;
    const done = (pattern, next, detail, confidence) => ({
      kind: 'sequence', pattern, nextValue: Math.round(next * 1e6) / 1e6,
      detail, confidence, sequence: seq,
    });

    if (seq.every((v) => v === seq[0])) return done('constant', seq[0], 'Every term is identical.', 0.99);
    const diffs = [];
    for (let i = 0; i < n - 1; i++) diffs.push(seq[i + 1] - seq[i]);
    const eqTol = (arr) => arr.every((d) => Math.abs(d - arr[0]) <= 1e-9 * Math.max(1, Math.abs(arr[0])));
    if (eqTol(diffs)) return done('arithmetic', seq[n - 1] + diffs[0], `Common difference ${diffs[0]}.`, 0.99);
    if (seq.every((v) => Math.abs(v) > 1e-12)) {
      const ratios = [];
      for (let i = 0; i < n - 1; i++) ratios.push(seq[i + 1] / seq[i]);
      if (eqTol(ratios)) return done('geometric', seq[n - 1] * ratios[0], `Common ratio ${ratios[0]}.`, 0.99);
    }
    // polynomial orders 2..3 via difference table
    let rows = [seq.slice(), diffs.slice()];
    for (let order = 2; order <= 3; order++) {
      const prev = rows[rows.length - 1];
      if (prev.length < 2) break;
      const next = [];
      for (let i = 0; i < prev.length - 1; i++) next.push(prev[i + 1] - prev[i]);
      rows.push(next);
      if (next.length >= 2 && eqTol(next)) {
        let add = next[next.length - 1];
        for (let r = rows.length - 2; r >= 0; r--) { add = rows[r][rows[r].length - 1] + add; rows[r].push(add); }
        return done(`polynomial_order_${order}`, rows[0][rows[0].length - 1],
          `Constant order-${order} differences (degree-${order} polynomial).`, 0.95);
      }
    }
    // repeating cycle (before recurrence — simpler explanation wins)
    for (let k = 1; k <= Math.floor(n / 2); k++) {
      const cycle = seq.slice(0, k);
      if (seq.every((v, i) => v === cycle[i % k]))
        return done('cyclic', cycle[n % k], `Repeating cycle of length ${k}.`, 0.98);
    }
    // linear recurrence order 2..3
    for (let order = 2; order <= 3; order++) {
      if (n >= 2 * order + 2) {
        const a = [], b = [];
        for (let i = order; i <= 2 * order; i++) {
          const row = [];
          for (let j = 1; j <= order; j++) row.push(seq[i - j]);
          row.push(1); a.push(row); b.push(seq[i]);
        }
        const coeffs = solveLinearSystem(a, b);
        if (coeffs) {
          const tol = 1e-6 * Math.max(1, ...seq.map(Math.abs));
          let ok = true;
          for (let i = order; i < n; i++) {
            let pred = 0;
            for (let j = 0; j < order; j++) pred += coeffs[j] * seq[i - 1 - j];
            pred += coeffs[order];
            if (Math.abs(pred - seq[i]) > tol) { ok = false; break; }
          }
          if (ok) {
            let nxt = 0;
            for (let j = 0; j < order; j++) nxt += coeffs[j] * seq[n - 1 - j];
            nxt += coeffs[order];
            const isFib = order === 2 && Math.abs(coeffs[0] - 1) < 1e-6 &&
              Math.abs(coeffs[1] - 1) < 1e-6 && Math.abs(coeffs[2]) < 1e-6;
            const terms = [];
            for (let j = 0; j < order; j++) terms.push(`${coeffs[j].toFixed(4)}·v[n-${j + 1}]`);
            terms.push(`${coeffs[order].toFixed(4)}`);
            return done(isFib ? 'fibonacci_like' : `linear_recurrence_order_${order}`, nxt,
              `v[n] = ${terms.join(' + ')}`, 0.97);
          }
        }
      }
    }
    const fb = forecastSeries(seq);
    if (fb.error) return fb;
    return Object.assign(fb, {
      pattern: 'none',
      detail: 'No exact rule detected; values come from a statistical forecast.',
      confidence: Math.min(fb.confidence || 0.4, 0.55),
    });
  }

  // ---------------------------------------------------------------- events
  function eventProbability(opts) {
    const { baseRate, successes, trials, evidence } = opts || {};
    const steps = [];
    if (successes != null && trials != null) {
      if (trials <= 0 || successes < 0 || successes > trials)
        return { error: 'Need 0 <= successes <= trials and trials >= 1.' };
      const m = (successes + 1) / (trials + 2);
      const sd = Math.sqrt((m * (1 - m)) / (trials + 3));
      return {
        kind: 'event_probability', mode: 'frequency',
        probability: Math.round(m * 10000) / 10000,
        interval95: [Math.round(Math.max(0, m - 1.96 * sd) * 10000) / 10000,
                     Math.round(Math.min(1, m + 1.96 * sd) * 10000) / 10000],
        reasoning: [`Observed ${successes} successes in ${trials} trials (Laplace-smoothed Beta posterior).`],
        confidence: r3(clamp(0.3 + trials / 50, 0.3, 0.9)),
      };
    }
    let p = baseRate == null ? 0.5 : baseRate;
    if (baseRate == null) steps.push('No base rate supplied; assuming an uninformative 50%.');
    else {
      if (!(p > 0 && p < 1)) return { error: 'Base rate must be strictly between 0 and 1.' };
      steps.push(`Starting from base rate ${(p * 100).toFixed(1)}%.`);
    }
    if (evidence && evidence.length) {
      let odds = p / (1 - p);
      evidence.forEach((ev) => {
        const dir = String(ev.direction || 'for').toLowerCase();
        const strength = clamp(Number(ev.strength == null ? 0.5 : ev.strength), 0, 1);
        const factor = Math.exp(strength * Math.log(4));
        if (['against', 'contra', 'negative', 'no'].includes(dir)) { odds /= factor; steps.push(`Evidence AGAINST (strength ${strength.toFixed(2)}): odds ÷ ${factor.toFixed(2)}.`); }
        else { odds *= factor; steps.push(`Evidence FOR (strength ${strength.toFixed(2)}): odds × ${factor.toFixed(2)}.`); }
      });
      p = odds / (1 + odds);
    }
    p = clamp(p, 0.01, 0.99);
    return {
      kind: 'event_probability', mode: 'base_rate_evidence',
      probability: Math.round(p * 10000) / 10000,
      probabilityPct: Math.round(p * 1000) / 10,
      reasoning: steps, confidence: evidence && evidence.length ? 0.6 : 0.5,
    };
  }

  // ---------------------------------------------------------------- risk
  function assessRisk(values, symbol = null) {
    if (values.length < 5) return { error: 'Need at least 5 data points for risk metrics.' };
    const rets = returns(values), vol = stdev(rets);
    const annualized = vol * Math.sqrt(252);
    let peak = values[0], maxDd = 0;
    values.forEach((v) => { peak = Math.max(peak, v); if (peak > 0) maxDd = Math.min(maxDd, (v - peak) / peak); });
    const var95 = percentile(rets.slice().sort((a, b) => a - b), 0.05);
    const recentVol = rets.length >= 5 ? stdev(rets.slice(-5)) : vol;
    const regime = vol > 0 && recentVol > vol * 1.25 ? 'expanding'
      : vol > 0 && recentVol < vol * 0.75 ? 'contracting' : 'stable';
    const { r2 } = ols(values.map((_, i) => i), values.map(Number));
    const score = clamp(
      Math.min(vol / 0.03, 1) * 4 + Math.min(Math.abs(maxDd) / 0.2, 1) * 3 +
      (1 - Math.max(r2, 0)) * 2 + (regime === 'expanding' ? 0.5 : 0), 0, 10);
    const label = score < 3 ? 'low' : score < 5.5 ? 'medium' : score < 8 ? 'high' : 'extreme';
    const out = {
      kind: 'risk', symbol: symbol || 'series',
      volatilityPerPeriod: Math.round(vol * 100000) / 100000,
      annualizedVolatilityPct: Math.round(annualized * 10000) / 100,
      maxDrawdownPct: Math.round(maxDd * 10000) / 100,
      historicalVar95Pct: Math.round(var95 * 10000) / 100,
      volatilityRegime: regime, trendStabilityR2: r3(r2),
      riskScore: Math.round(score * 100) / 100, riskLabel: label,
      dataPoints: values.length, disclaimer: DISCLAIMER,
    };
    if (values.length < 20)
      out.warnings = [`Only ${values.length} data points; estimates are coarse. 20+ is recommended.`];
    return out;
  }

  function analyzeMarket(values, symbol = null) {
    const direction = predictDirection(values, symbol);
    if (direction.error) return direction;
    const ind = indicators(values);
    return {
      kind: 'market_brief', symbol: symbol || 'series', direction,
      scenarios: scenarios(values, symbol).scenarios,
      risk: assessRisk(values, symbol),
      indicators: { rsi: ind.rsi, support: direction.support, resistance: direction.resistance },
      confidence: direction.confidence, disclaimer: DISCLAIMER,
    };
  }

  // ---------------------------------------------------------------- autotrade
  const TRADER_DEFAULTS = {
    startingEquity: 10000, positionFraction: 0.10, confidenceMin: 0.60,
    probMin: 0.60, stopLossPct: 0.03, takeProfitPct: 0.06, commissionBps: 10,
    slippageBps: 5, maxDrawdownKill: 0.20, maxConsecutiveLosses: 5,
    warmup: 12, allowShort: false,
  };
  const PAPER_NOTE = 'Paper execution only — simulated fills, no exchange contacted, no real ' +
    'money. Past (simulated) performance never guarantees future results.';

  function autoTrade(series, overrides) {
    const cfg = Object.assign({}, TRADER_DEFAULTS, overrides || {});
    series = series.map(Number);
    const costs = (price, qty) => price * qty * (cfg.commissionBps / 10000);
    let cash = cfg.startingEquity, position = null, realizedPnl = 0, fills = 0;
    let armed = true, killed = false, killReason = '';
    let consecutiveLosses = 0, peak = cfg.startingEquity;
    const trades = [], equityCurve = [], prices = [], actions = [];

    const r4 = (x) => Math.round(x * 10000) / 10000;

    function buy(index, price) {
      if (position) return null;
      const slipped = price * (1 + cfg.slippageBps / 10000);
      if (slipped <= 0 || cash <= 0) return null;
      const budget = Math.min(cash * cfg.positionFraction, cash);
      let qty = budget / slipped;
      while (qty > 0) {
        const cost = qty * slipped + costs(slipped, qty);
        if (cost <= budget * 1.0000001) break;
        qty *= 0.999;
      }
      const cost = qty * slipped + costs(slipped, qty);
      if (qty <= 0 || cost > cash) return null;
      cash -= cost; fills++;
      position = {
        side: 'long', entryIndex: index, entryPrice: slipped, quantity: qty,
        stopPrice: slipped * (1 - cfg.stopLossPct),
        targetPrice: slipped * (1 + cfg.takeProfitPct),
      };
      return position;
    }
    function close(index, price, reason) {
      if (!position) return null;
      const slipped = price * (1 - cfg.slippageBps / 10000);
      const proceeds = slipped * position.quantity - costs(slipped, position.quantity);
      cash += proceeds; fills++;
      const pnl = proceeds - (position.entryPrice * position.quantity +
        costs(position.entryPrice, position.quantity));
      realizedPnl += pnl;
      const trade = {
        side: position.side, entryIndex: position.entryIndex,
        entryPrice: position.entryPrice, exitIndex: index, exitPrice: slipped,
        quantity: position.quantity, pnl: r4(pnl), reason,
      };
      position = null;
      return trade;
    }
    function kill(reason) {
      killed = true; killReason = reason;
      if (position && prices.length) {
        const t = close(prices.length - 1, prices[prices.length - 1], 'manual');
        if (t) record(t);
      }
      armed = false;
      actions.push('KILL SWITCH: ' + reason);
    }
    function record(trade) {
      trades.push(trade);
      if (trade.pnl < 0) {
        consecutiveLosses++;
        if (consecutiveLosses >= cfg.maxConsecutiveLosses) kill(consecutiveLosses + ' consecutive losses');
      } else consecutiveLosses = 0;
    }

    // ---- the autonomous loop, one bar at a time ----
    for (let i = 0; i < series.length; i++) {
      const price = series[i];
      prices.push(price);
      const eq = position ? cash + position.quantity * price : cash;
      equityCurve.push(r4(eq));
      if (eq > peak) peak = eq;

      // 1) drawdown kill switch runs whenever a position exists
      if (position && 1 - eq / peak >= cfg.maxDrawdownKill) {
        kill('max drawdown breached');
        continue;
      }
      if (killed || !armed || i < cfg.warmup) continue;

      // 2) exits: stop / target
      if (position) {
        let reason = null;
        if (price <= position.stopPrice) reason = 'stop_loss';
        else if (price >= position.targetPrice) reason = 'take_profit';
        if (reason) {
          const t = close(i, price, reason);
          if (t) record(t);
        }
      }

      // 3) exit on confident opposite signal
      if (position && prices.length >= 6) {
        const pred = predictDirection(prices);
        if (pred.verdict === 'DOWN' && pred.confidence >= cfg.confidenceMin) {
          const t = close(i, price, 'signal_flip');
          if (t) record(t);
        }
      }

      // 4) entry on a confident UP signal
      if (!position && !killed && prices.length >= 6) {
        const pred = predictDirection(prices);
        if (pred.verdict === 'UP' && pred.confidence >= cfg.confidenceMin &&
            pred.probabilities.up >= cfg.probMin) buy(i, price);
      }
    }
    // disarm + flatten
    if (position && prices.length) {
      const t = close(prices.length - 1, prices[prices.length - 1], 'manual');
      if (t) record(t);
    }
    armed = false;

    // ---- report ----
    const curve = equityCurve.length ? equityCurve : [cfg.startingEquity];
    const final = curve[curve.length - 1];
    const totalReturn = final / cfg.startingEquity - 1;
    const startI = Math.min(cfg.warmup, prices.length - 1);
    const bh = prices.length >= 2 && prices[0]
      ? prices[prices.length - 1] / prices[startI] - 1 : 0;
    let pk = curve[0], maxDd = 0;
    curve.forEach((e2) => { if (e2 > pk) pk = e2; if (pk > 0) maxDd = Math.min(maxDd, e2 / pk - 1); });
    const wins = trades.filter((t) => t.pnl > 0), losses = trades.filter((t) => t.pnl <= 0);
    const grossWin = wins.reduce((a, t) => a + t.pnl, 0);
    const grossLoss = Math.abs(losses.reduce((a, t) => a + t.pnl, 0));
    const rets = [];
    for (let i = 1; i < curve.length; i++) if (curve[i - 1] > 0) rets.push(curve[i] / curve[i - 1] - 1);
    let sharpe = 0;
    if (rets.length > 2) {
      const m = rets.reduce((a, b) => a + b, 0) / rets.length;
      const sd = Math.sqrt(rets.reduce((a, r) => a + (r - m) ** 2, 0) / (rets.length - 1));
      sharpe = sd > 0 ? (m / sd) * Math.sqrt(252) : 0;
    }
    return {
      kind: 'autotrade', mode: 'paper', bars: prices.length, armed, killed,
      killReason: killReason || null, startingEquity: cfg.startingEquity,
      finalEquity: Math.round(final * 100) / 100,
      totalReturnPct: Math.round(totalReturn * 10000) / 100,
      buyHoldReturnPct: Math.round(bh * 10000) / 100,
      openPosition: null, trades, tradeCount: trades.length,
      winRate: trades.length ? r4(wins.length / trades.length) : null,
      wins: wins.length, losses: losses.length,
      profitFactor: grossLoss > 0 ? Math.round((grossWin / grossLoss) * 100) / 100
        : (wins.length ? Infinity : null),
      maxDrawdownPct: Math.round(maxDd * 10000) / 100,
      sharpe: Math.round(sharpe * 100) / 100,
      fills, realizedPnl: Math.round(realizedPnl * 100) / 100,
      equityCurve: curve, actions, disclaimer: PAPER_NOTE,
    };
  }
  function backtest(values, warmup = 12, confidenceThreshold = 0.6) {
    values = values.map(Number);
    const n = values.length;
    if (n < warmup + 5) return { error: `Need at least ${warmup + 5} points (got ${n}).` };
    let hits = 0, total = 0, confHits = 0, confTotal = 0;
    let brierJ = 0, brierCoin = 0, brierMom = 0;
    const verdictCounts = { UP: 0, DOWN: 0, SIDEWAYS: 0 };
    let fcErr = 0, naiveErr = 0, fcPts = 0;
    const buckets = { '50-60%': [0, 0], '60-70%': [0, 0], '70-80%': [0, 0], '80%+': [0, 0] };

    for (let i = warmup; i < n - 1; i++) {
      const window = values.slice(0, i + 1);
      const ret = values[i] ? (values[i + 1] - values[i]) / values[i] : 0;
      const outcomeUp = ret > 0 ? 1 : 0;
      const pred = predictDirection(window);
      if (pred.error) continue;

      total++;
      verdictCounts[pred.verdict]++;
      const correct = (pred.verdict === 'UP' && ret > 0) || (pred.verdict === 'DOWN' && ret < 0);
      if (correct) hits++;

      const conf = pred.confidence;
      if (conf >= confidenceThreshold) { confTotal++; if (correct) confHits++; }

      const denom = Math.max(pred.probabilities.up + pred.probabilities.down, 1e-9);
      const pUp = pred.probabilities.up / denom;
      brierJ += (pUp - outcomeUp) ** 2;
      brierCoin += (0.5 - outcomeUp) ** 2;
      const lastRet = values[i - 1] ? (values[i] - values[i - 1]) / values[i - 1] : 0;
      brierMom += ((lastRet > 0 ? 1 : 0) - outcomeUp) ** 2;

      const pct = conf * 100;
      const key = pct < 60 ? '50-60%' : pct < 70 ? '60-70%' : pct < 80 ? '70-80%' : '80%+';
      buckets[key][1]++;
      if (correct) buckets[key][0]++;

      if (i % 5 === 0) {
        const fc = forecastSeries(window);
        if (!fc.error) {
          fcPts++;
          fcErr += Math.abs(fc.nextValue - values[i + 1]);
          naiveErr += Math.abs(values[i] - values[i + 1]);
        }
      }
    }
    if (total === 0) return { error: 'No scored predictions (series too short).' };

    const grade = (hr, br) =>
      (br < 0.2 && hr >= 0.6) ? 'edge: model beat both baselines on this data'
        : hr >= 0.55 ? 'weak edge: slightly better than a coin flip'
        : Math.abs(hr - 0.5) < 0.05 ? 'no measurable edge on this data'
        : 'model underperformed on this data — do not trust it here';

    const r4 = (x) => Math.round(x * 10000) / 10000;
    return {
      kind: 'backtest', points: n, predictions: total, warmup,
      hitRate: Math.round((hits / total) * 1000) / 1000,
      confidentHitRate: confTotal ? Math.round((confHits / confTotal) * 1000) / 1000 : null,
      confidentShare: Math.round((confTotal / total) * 1000) / 1000,
      brier: r4(brierJ / total), brierCoinFlip: r4(brierCoin / total),
      brierMomentum: r4(brierMom / total),
      verdictMix: verdictCounts,
      forecastMae: fcPts ? Math.round((fcErr / fcPts) * 10000) / 10000 : null,
      naiveMae: fcPts ? Math.round((naiveErr / fcPts) * 10000) / 10000 : null,
      calibration: Object.entries(buckets).filter(([, v]) => v[1])
        .map(([bucket, v]) => ({ bucket, hitRate: Math.round((v[0] / v[1]) * 1000) / 1000, n: v[1] })),
      verdict: grade(hits / total, brierJ / total),
      note: 'Walk-forward, zero look-ahead. Past accuracy never guarantees future results.',
    };
  }

  // ---------------------------------------------------------------- parsing
  function extractSeries(text) {
    const m = String(text || '').match(/-?\d+(\.\d+)?/g);
    const nums = m ? m.map(Number) : [];
    return nums.length >= 3 ? nums : [];
  }
  const CRYPTO = { btc: 'BTC', bitcoin: 'BTC', eth: 'ETH', ethereum: 'ETH', sol: 'SOL', doge: 'DOGE', xrp: 'XRP' };
  function extractSymbol(text) {
    const low = String(text || '').toLowerCase();
    for (const [alias, sym] of Object.entries(CRYPTO)) if (new RegExp(`\\b${alias}\\b`).test(low)) return sym;
    const stops = new Set(['HELP', 'QUIT', 'EXIT', 'RESET', 'SHOW', 'LOAD', 'JSON', 'DEMO', 'THE', 'AND', 'FOR', 'NEXT', 'WHAT', 'WILL', 'IT', 'GO', 'IS', 'MY', 'ME', 'UP', 'OR', 'IN', 'OF', 'TO', 'ON', 'BE', 'DO', 'AT']);
    const caps = String(text || '').match(/\b[A-Z]{2,5}\b/g) || [];
    const t = caps.find((c) => !stops.has(c));
    return t || null;
  }

  return {
    DISCLAIMER, indicators, predictDirection, scenarios, forecastSeries,
    predictSequence, eventProbability, assessRisk, analyzeMarket, backtest,
    autoTrade, extractSeries, extractSymbol,
  };
});
