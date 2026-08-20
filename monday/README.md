# Monday - Multi-AI Personal Operating System

## Overview

Monday is a multi-AI orchestration platform, personal AI assistant, computer automation system, and software development environment.

## Architecture

```
                         USER
                           │
                           ▼
                  ┌─────────────────┐
                  │     MONDAY      │
                  │   AI ORCHESTRATOR│
                  │      BRAIN      │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  TASK ANALYZER  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  TASK PLANNER   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  ROUTER /       │
                  │  AGENT MANAGER  │
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   CODING AGENT      RESEARCH AGENT     CREATIVE AGENT
                                            
                          ▼
                  ┌─────────────────┐
                  │ PREDICTION AGENT│  (Jarvis)
                  │ "what happens   │
                  │   next" only    │
                  └─────────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
   DeepSeek/other       Web tools        Qwen/image AI
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ VALIDATION      │
                  │ & TESTING       │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ AUTOMATION      │
                  │ ENGINE          │
                  └────────┬────────┘
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
             LAPTOP                PHONE
          EXECUTION LAYER       COMPANION APP
```

## Core Principles

1. **ONE BRAIN + MANY SPECIALISTS + MANY TOOLS**
2. **Laptop-first architecture** - Phone connects as companion device
3. **Model abstraction** - Never hard-code around a single AI provider
4. **Intelligent routing** - Choose the right model for each task
5. **Validation layer** - Verify all outputs before execution
6. **Failure recovery** - Design around the assumption that things will fail
7. **Human oversight** - Distinguish between autonomous, confirmed, and prohibited actions
8. **THINKING vs ACTING separation** - AI reasons, tools execute with permission

## Directory Structure

```
monday/
├── core/               # Core brain, orchestrator, task analyzer, planner
├── agents/             # Specialist agents (coding, prediction/Jarvis, ...)
├── jarvis.py           # Jarvis prediction console (python -m monday.jarvis)
├── app/                # Jarvis as a downloadable offline app (single-file + PWA)
├── tools/              # Tool execution layer (browser, terminal, files, android, git, builds)
├── memory/             # Short-term, task, project, long-term preferences, knowledge memory
├── automation/         # Automation engine and executors (Windows, Browser, Android, File, Shell)
├── models/             # Model providers, registry, routing, fallback
├── validation/         # Validation layer for code, research, creative, automation
├── software_factory/   # Software development pipeline
├── game_factory/       # Game development agent
├── creative/           # Creative agent for images, posters, graphics
├── research/           # Research agent for web search and information gathering
├── browser/            # Browser automation agent
├── social/             # Social media agent
├── android_gateway/    # Secure connection to Android companion app
├── config/             # Configuration and secret management
├── dashboard/          # Observability dashboard
└── observability/      # Internal monitoring and metrics
```

## Getting Started

### Prerequisites

- Python 3.10+
- API keys for AI providers (configured in `config/secrets.env`)
- Optional: Android Studio for companion app development

### Installation

```bash
# Clone the repository
cd monday

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp config/secrets.env.example config/secrets.env
# Edit config/secrets.env with your API keys

# Run Monday
python -m monday.core.main
```

### Configuration

Edit `config/settings.yaml` to customize:

- Default AI models
- Automation permissions
- Memory settings
- Agent configurations

## Usage Examples

### Create an App

```
"Monday, create an app for managing my school timetable."
```

Monday will:
1. Analyze the request
2. Generate requirements and specification
3. Create architecture
4. Generate code through the Coding Agent
5. Build and test through the Software Factory
6. Return the completed project

### Research Task

```
"Monday, research the best Kotlin tutorials for beginners."
```

Monday will:
1. Route to Research Agent
2. Search the web
3. Gather and compare sources
4. Summarize findings with references

### Predictions (Jarvis)

```
"Monday, predict the next number in 2 4 8 16 32"
"Monday, will BTC go up or down? prices 44000 44500 44100 45200 45800"
```

Monday routes these to **Jarvis**, the prediction-only specialist:

1. Direction probabilities (up / down / sideways) from six transparent
   signals (momentum, EMA crossover, trend slope, RSI extremes,
   mean reversion, MACD)
2. Next-value forecasts with 80% / 95% intervals (trend + Holt
   exponential smoothing + SMA ensemble, weighted by walk-forward error)
3. Sequence solving (arithmetic, geometric, polynomial, linear
   recurrence, cycles)
4. Event odds (Laplace-smoothed frequencies, base rate + evidence
   log-odds updates)
5. Risk metrics (volatility, max drawdown, historical VaR 95%)

**Measure before you trust it** — the walk-forward backtest scores the
direction model on your own data with zero look-ahead:

```
python -m monday.backtest prices.csv          # your series
python -m monday.backtest --demo              # seeded demo
```

It reports hit rate, Brier score vs coin-flip/momentum baselines, forecast
MAE vs naive, and confidence calibration — and says plainly when there is
*no measurable edge* (e.g. on pure random walks).

Or talk to Jarvis directly — fully offline, no API keys:

```
python -m monday.jarvis                       # interactive console
python -m monday.jarvis "next number in 2 4 8 16 32"
python -m monday.jarvis --file prices.txt "direction"
python -m monday.jarvis "..." --json          # machine-readable
python -m monday.jarvis --demo
```

> Every market output carries an explicit disclaimer: these are
> transparent statistical estimates, **not financial advice**.

**Autonomous trading — on command, on paper.** Jarvis arms when you say so
and then trades entirely on its own: signal → risk check → sized entry →
stop-loss/take-profit/signal-flip exits → P&L, with a drawdown kill switch
and a consecutive-loss circuit breaker. **Paper mode only**: simulated
fills (commission + slippage modeled), no exchange contacted, no keys.

```
python -m monday.trader prices.csv            # arms, trades the whole series, reports
python -m monday.trader --demo
# in the Jarvis console / app: "autotrade"  (or the ⚡ Auto-trade chip)
```

### Live prices (and testnet execution)

```bash
python -m monday.live                        # live testnet prices → paper fills
python -m monday.live --symbol ETHUSDT --interval 5m
python -m monday.live --execute              # + REAL orders on the spot TESTNET
python -m monday.live --bars 30              # auto-stop, disarm, full report
```

`--execute` mirrors every paper fill as a MARKET order on the **Binance
spot TESTNET** — real API mechanics and order lifecycle, fake funds. To
enable it:

1. Create free testnet keys: <https://testnet.binance.vision>
2. `cp monday/config/secrets.env.example monday/config/secrets.env` and fill
   in `BINANCE_TESTNET_KEY` / `BINANCE_TESTNET_SECRET`
   (that file is gitignored; keys are never logged or accepted in code
   review chat)

Mainnet is refused by construction — `monday/brokers.py` contains no
mainnet URL and rejects any other host (`SafetyError`). Real-money wiring
is deliberately absent. If you ever add it yourself: testnet first, keep
the risk limits, and re-read the backtest.

The **app** also has a live mode (● Go live): it streams real Binance
candles into the chart from your browser and can auto-trade each new bar
on the paper account — no keys needed for market data.

**As a downloadable app** — Jarvis also ships as an offline single-file web
app (plus installable PWA) in [`monday/app/`](app/README.md):

```
monday/app/jarvis-app.html    # one file — download, open anywhere, works offline
python -m http.server 8080    # or host the folder and "Add to Home Screen"
```

### Creative Task

```
"Monday, make a poster for my school event."
```

Monday will:
1. Route to Creative Agent
2. Generate design specifications
3. Use image generation model
4. Validate quality
5. Return the poster

### Automation Task

```
"Monday, open Chrome and search for the best Kotlin tutorials."
```

Monday will:
1. Route to Browser Agent
2. Open Chrome
3. Navigate to search engine
4. Perform search
5. Verify result

## Security

- API keys stored in environment variables, never in source code
- Secure authentication between laptop and Android companion
- Encrypted communication
- Device pairing required
- Permission-based action execution

## Extensibility

New agents can be added without redesigning the entire system:

```python
from monday.core.agent import BaseAgent

class FinanceAgent(BaseAgent):
    def __init__(self):
        super().__init__("finance")
    
    def execute(self, task):
        # Implement finance-specific logic
        pass
```

Register the agent in `core/agent_registry.py`.

## License

MIT License

## Contributing

See CONTRIBUTING.md for guidelines on contributing to Monday.
