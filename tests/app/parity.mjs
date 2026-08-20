/*
 * Parity harness: run engine.js and prediction_agent.py on the same inputs and
 * compare. Python side is driven through a small subprocess bridge — see
 * tests/app/python_bridge.py. Usage: node tests/app/parity.mjs
 */
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..');
const E = require(path.join(root, 'monday/app/engine.js'));

const py = (expr) =>
  JSON.parse(execFileSync('python3', ['-c', `
import sys, json
sys.path.insert(0, r"${root}")
from monday.agents.prediction_agent import PredictionAgent
a = PredictionAgent()
print(json.dumps(${expr}))
`], { cwd: root }));

const pyScript = (script) =>
  JSON.parse(execFileSync('python3', ['-c', script.replace('{ROOT}', root)], { cwd: root }));

let failures = 0;
const close = (a, b, tol, label) => {
  const d = Math.abs(a - b);
  if (!(d <= tol)) { console.error(`✗ ${label}: js=${a} py=${b} (Δ${d.toFixed(6)})`); failures++; }
};
const eq = (a, b, label) => {
  if (a !== b) { console.error(`✗ ${label}: js=${JSON.stringify(a)} py=${JSON.stringify(b)}`); failures++; }
};

const SERIES = {
  up: Array.from({ length: 15 }, (_, i) => 100 + i * 2),
  down: Array.from({ length: 15 }, (_, i) => 130 - i * 2),
  noisy: [100.2, 101.1, 99.8, 100.9, 101.7, 102.4, 101.9, 102.8, 103.5, 103.1, 104.2, 105.0],
  short: [5, 6, 8, 7, 9, 11, 10, 12],
};

// ---- direction parity
for (const [name, s] of Object.entries(SERIES)) {
  const js = E.predictDirection(s, 'T');
  const p = py(`a.predict_direction([${s.join(',')}], symbol='T')`);
  eq(js.verdict, p.verdict, `dir.verdict ${name}`);
  close(js.probabilities.up, p.probabilities.up, 0.002, `dir.pUp ${name}`);
  close(js.probabilities.down, p.probabilities.down, 0.002, `dir.pDown ${name}`);
  close(js.confidence, p.confidence, 0.005, `dir.conf ${name}`);
  close(js.netScore, p.net_score, 0.002, `dir.net ${name}`);
  eq(js.signals.length, 6, `dir.signals ${name}`);
}

// ---- forecast parity
for (const [name, s] of Object.entries(SERIES)) {
  const js = E.forecastSeries(s, 3);
  const p = py(`a.forecast_series([${s.join(',')}], horizon=3)`);
  close(js.nextValue, p.next_value, 0.02, `fc.next ${name}`);
  close(js.interval80[0], p.interval_80[0], 0.05, `fc.lo80 ${name}`);
  close(js.interval80[1], p.interval_80[1], 0.05, `fc.hi80 ${name}`);
  close(js.confidence, p.confidence, 0.02, `fc.conf ${name}`);
}

// ---- sequence parity
const SEQS = [
  [2, 4, 6, 8], [2, 4, 8, 16, 32], [1, 1, 2, 3, 5, 8], [1, 4, 9, 16, 25],
  [1, 8, 27, 64, 125], [3, 1, 4, 3, 1, 4], [1, 1, 3, 7, 17, 41],
  [4, 7, 1, 9, 3], [10, 12, 11, 14, 13, 16],
];
for (const q of SEQS) {
  const js = E.predictSequence(q);
  const p = py(`a.predict_sequence([${q.join(',')}])`);
  eq(js.pattern, p.pattern, `seq.pattern [${q}]`);
  close(js.nextValue, p.next_value, 1e-6, `seq.next [${q}]`);
}

// ---- event parity
const ev1 = E.eventProbability({ successes: 7, trials: 10 });
const pe1 = py(`a.event_probability(successes=7, trials=10)`);
close(ev1.probability, pe1.probability, 1e-6, 'event.freq');
close(ev1.interval95[1], pe1.interval_95[1], 1e-6, 'event.freq.hi');
const ev2 = E.eventProbability({ baseRate: 0.3, evidence: [{ direction: 'for', strength: 0.7 }] });
const pe2 = py(`a.event_probability(base_rate=0.3, evidence=[{'direction':'for','strength':0.7}])`);
close(ev2.probability, pe2.probability, 1e-6, 'event.base');

// ---- risk parity
const rj = E.assessRisk(SERIES.noisy, 'T');
const rp = py(`a.assess_risk([${SERIES.noisy.join(',')}], symbol='T')`);
eq(rj.riskLabel, rp.risk_label, 'risk.label');
close(rj.riskScore, rp.risk_score, 0.05, 'risk.score');
close(rj.maxDrawdownPct, rp.max_drawdown_pct, 0.01, 'risk.dd');
eq(rj.volatilityRegime, rp.volatility_regime, 'risk.regime');

// ---- scenarios parity
const sj = E.scenarios(SERIES.noisy, 'T');
const sp = py(`a.scenarios([${SERIES.noisy.join(',')}], symbol='T')`);
sj.scenarios.forEach((s, i) => {
  eq(s.name, sp.scenarios[i].name, 'scen.name');
  close(s.probability, sp.scenarios[i].probability, 0.01, 'scen.p');
  close(s.target, sp.scenarios[i].target, 0.05, 'scen.target');
});

// ---- backtest parity (JS and Python must score identically on the same series)
const pySeries = pyScript(`
import sys, json, random
sys.path.insert(0, r"{ROOT}")
rng = random.Random(42)
v, series = 100.0, []
for _ in range(120):
    v *= 1.0 + rng.gauss(0.002, 0.008)
    series.append(round(v, 4))
print(json.dumps(series))
`);
const pb = pyScript(`
import sys, json
sys.path.insert(0, r"{ROOT}")
series = json.loads('''${JSON.stringify(pySeries)}''')
from monday.backtest import backtest
print(json.dumps(backtest(series)))
`);
const jsBack = E.backtest(pySeries, 12, 0.6);
eq(jsBack.predictions, pb.predictions, 'bt.predictions');
close(jsBack.hitRate, pb.hit_rate, 0.002, 'bt.hitRate');
close(jsBack.brier, pb.brier, 0.005, 'bt.brier');
close(jsBack.brierMomentum, pb.brier_momentum, 0.005, 'bt.brierMom');
eq(jsBack.verdictMix.UP, pb.verdict_mix.UP, 'bt.mix.UP');
eq(jsBack.verdictMix.DOWN, pb.verdict_mix.DOWN, 'bt.mix.DOWN');
eq(jsBack.forecastMae != null, pb.forecast_mae != null, 'bt.fc presence');
close(jsBack.forecastMae, pb.forecast_mae, 0.01, 'bt.forecastMae');

console.log(failures === 0 ? `✓ parity OK (${SERIES.up.length}-pt series, ${SEQS.length} sequences, events, risk, scenarios, backtest)`
  : `✗ ${failures} parity failures`);
process.exit(failures === 0 ? 0 : 1);
