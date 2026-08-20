# Jarvis on real market data — the honest scoreboard

**Data:** 366 daily closes of BTC/USD, 2025-08-21 → 2026-08-20 (CoinGecko).
A brutal year: ~114k start, peak ~124.7k (Oct 2025), crash to ~58.6k
(Jun 2026), recovery to ~72.5k. **Buy & hold: −36.5%.**

Reproduce everything:

```bash
python -m monday.backtest monday/examples/btc_usd_daily.csv
python -m monday.trader  monday/examples/btc_usd_daily.csv
```

## Backtest (walk-forward, no look-ahead)

| Metric | Result | Read |
|---|---|---|
| Directional hit rate | **45.3%** | worse than a coin flip |
| Brier score | **0.283** | worse than 0.250 (coin) |
| Confident calls (≥60%) | 57.1% (only 6% of calls) | mildly better when sure |
| Forecast MAE | 1,886 vs naive 1,401 | ensemble worse than "repeat last" |
| Verdict mix | 142 UP / 187 DOWN / 24 flat | bear-aware but not predictive |
| **Verdict** | **no measurable edge on this data** | |

## Autonomous paper trading (armed the whole year)

| Metric | Jarvis | Buy & hold |
|---|---|---|
| Return | **0.00%** | **−33.63%** |
| Trades | 0 | — |
| Max drawdown | 0.00% | ~−53% |

The confidence gate (verdict UP **and** confidence ≥ 0.60 **and** P(up) ≥ 0.60)
never fired in a year of downtrend and chop. Jarvis stayed flat for 366 bars.

## Interpretation — read this before trusting the bot

1. **The model has no directional edge here.** 45.3% hit rate, worse-than-coin
   Brier. Anyone selling you a rule-based daily direction model for BTC should
   be able to show you numbers like these — most never do.
2. **"Flat beat holding by 33 points" is capital preservation, not alpha.**
   Being out of a crashing market looks great in hindsight; in a bull year the
   same skepticism means missing gains. A strategy that never trades has zero
   edge and zero risk — that is exactly what the scoreboard is showing.
3. **The gates did their job.** The risk-first design (confidence thresholds,
   long-only, sizing caps) refused to force trades into a market it could not
   read. That is the correct behavior for an honest system.

**Conclusion:** on this data, do not let this model trade real money — the
backtest says so in its own words. The testnet and paper layers exist so this
verdict stays cheap to obtain. Re-run this file's commands on YOUR market and
timeframe before changing anything.

*Generated 2026-08-20. Past performance never guarantees future results.*
