# Jarvis — the app

The Jarvis prediction engine as a downloadable, offline, installable app.
No accounts, no servers, no API keys — everything runs in the browser.

## Get it (pick one)

**A. Download the single-file app** — `jarvis-app.html` (~53 KiB)

1. Download `jarvis-app.html`
2. Open it in any browser — phone, tablet, laptop. That's it. It works
   with no internet, forever, because the whole engine is inside the file.

**B. Install it as an app (PWA)** — when hosted, e.g. from the live preview

1. Open the app URL in Chrome / Safari
2. **Android/desktop Chrome:** menu → *Install app* / *Add to Chrome*
3. **iOS Safari:** Share → *Add to Home Screen*

It launches full-screen from your home screen with its own icon and keeps
working offline (service worker caches everything after first load).

**C. Rebuild the single file** after editing `engine.js` or `index.html`:

```bash
python3 monday/app/build_standalone.py   # -> monday/app/jarvis-app.html
```

## What's inside

| File | Purpose |
|---|---|
| `index.html` | App UI (data panel, charts, quick actions, chat) |
| `engine.js` | JS port of `monday/agents/prediction_agent.py` (parity-tested) |
| `manifest.webmanifest`, `sw.js`, `icon.svg` | PWA install + offline cache |
| `jarvis-app.html` | Standalone single-file build (generated) |
| `build_standalone.py` | Inlines engine + icon into the single file |

## Using it

1. **Data** — paste a price series (`101 103 99 105 108`), load a CSV/TXT
   file, or tap *Demo data*. State persists in your browser.
2. **Ask** — tap a chip (*Direction, Next value, Scenarios, Risk, Full
   brief, Sequence puzzle, Event odds*) or type naturally:
   - `will it go up or down`
   - `next number in 2 4 8 16 32`
   - `odds 7 of 10` · `odds base 30% strong evidence for`
3. **Read** — probability bars, signal breakdown, forecast with 80/95%
   intervals on the chart, bull/base/bear targets, risk gauge.

Every market answer carries the disclaimer: transparent statistical
estimates, **not financial advice**.
