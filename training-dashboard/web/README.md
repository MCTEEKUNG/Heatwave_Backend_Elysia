# Heatwave Training Dashboard (web)

A dev-only Vite + React + TypeScript single-page dashboard that connects to the
training server over WebSocket and renders live training progress.

- Dashboard dev server: **http://127.0.0.1:5173**
- Training server WebSocket: **ws://127.0.0.1:8000/ws** (owned by the Python server agent)

The dashboard opens the WebSocket directly (no proxy). It auto-reconnects with
capped exponential backoff and degrades gracefully when the server is offline —
the header shows `connecting… / connected / disconnected` and it keeps retrying
without crashing.

## Requirements

- [bun](https://bun.sh) (tested with 1.3.10). Use bun for everything — do not use
  npm/node directly.

## Commands

Run all commands from `training-dashboard/web`.

```sh
# install dependencies
bun install

# run the dev server (serves on http://127.0.0.1:5173)
bun run dev

# production build (runs tsc + vite build, must complete with no errors)
bun run build

# run the unit tests headlessly (vitest)
bunx vitest run
# or: bun run test
```

## Protocol

The client speaks the frozen protocol contract.

Client -> server (JSON text frames):

```json
{ "command": "start", "trainer": "simulated", "config": { "total_steps": 10000, "speed_per_sec": 100 } }
{ "command": "stop" }
```

Server -> client events (`type`): `status`, `log`, `metrics`, `error`.

## Structure

- `src/protocol.ts` — frozen protocol types (client commands + server events).
- `src/ws.ts` — auto-reconnecting `WsClient` plus the pure, unit-tested
  `reduce(state, event)` reducer and `setConnection` helper.
- `src/components/`
  - `ProgressBar.tsx` — percentage bar + `step X / Y`.
  - `SpeedChart.tsx` — lightweight inline-SVG sparkline of `speed_per_sec`
    (no charting library).
  - `Eta.tsx` — exports the pure `formatEta(seconds)` (e.g. `108 -> "1 m 48 s"`).
  - `LogPanel.tsx` — auto-scrolling, level-colored log list.
  - `Controls.tsx` — trainer select + Start/Stop buttons.
  - `MetricsPanel.tsx` — pretty key/value tree of the final metrics report.
  - `Toast.tsx` — transient toast + browser `Notification` on done/error.
- `src/App.tsx` — layout and wiring.

## Tests

`bunx vitest run` (jsdom env) covers:

- `formatEta` — `108 -> "1 m 48 s"`, `8100 -> "2 h 15 m"`, `0`/`null` -> `—`.
- `reduce` — folding `status -> status -> done -> metrics` yields the expected
  UI state (progress/step update, `speedHistory` grows, `metrics` set, state
  transitions preserved), plus log/error/purity checks.
