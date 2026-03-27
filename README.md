# CodexOne · CL1 Simulator

A Next.js front end and local APIs for a **CL1-style MEA simulator**: tick loops, synthetic spike output, stimulation, and recording — for building and testing without hardware.

**Development:** This repository was programmed primarily with [**Cursor Composer 2**](https://cursor.com) using **fully lazy prompting** — short, low-effort prompts with little up-front spec — mostly to get a feel for how the model behaves in practice. Human direction, review, and integration remain the owner’s responsibility.

Dashboard **layout and UX** are specified in [`docs/PRD-dashboard-layout.md`](docs/PRD-dashboard-layout.md).

## What’s included

| Piece | Description |
|--------|-------------|
| **Next.js app** | Dashboard + route handlers under `app/api/simulator/*` |
| **TS mock** | In-process simulator (`lib/simulator/`) used by the dashboard and APIs |
| **Python `cl_sim`** | Optional CL-compatible runtime (`cl.open()`); see [`docs/python-cl-simulator.md`](docs/python-cl-simulator.md) |

### CL1 reference material (concepts beyond this mock)

- [`docs/CL1-model-patterns.md`](docs/CL1-model-patterns.md) — baselines, SFE, readout ablations, feedback, hardware-aware training  
- [`docs/CL1-operations-patterns.md`](docs/CL1-operations-patterns.md) — ports, control vs. data plane, recording, observability  
- [`docs/CL1-udp-protocol.md`](docs/CL1-udp-protocol.md) — channel mask, validation, example binary packets, timing  

### In-repo CL1 mock (TypeScript)

- [`lib/simulator/cl1-constants.ts`](lib/simulator/cl1-constants.ts) — 64 electrodes, dead-channel mask `{0,4,7,56,63}`, 59 stimulable IDs, spike normalizer `clamp / 35`  
- [`lib/simulator/packets.ts`](lib/simulator/packets.ts) — `packStimPacket` / `packSpikePacket` (520 B / 264 B), aligned with [`scripts/cl1_multiport_protocol_helper.py`](scripts/cl1_multiport_protocol_helper.py)  
- [`lib/simulator/core.ts`](lib/simulator/core.ts) — tick loop fills per-tick **`cl1`** frames (freq/µA arrays + spike counts); stimulation on dead channels is rejected  

Additional **Python helpers** (CLI / offline checks): [`scripts/README.md`](scripts/README.md). Human-readable reference copies: [`references/`](references/).

## Requirements

- **Node.js** (for `npm install` / Next 16)  
- **Python ≥ 3.10 — only for `cl_sim` / `npm run python:service`  

## Quick start

```bash
npm install
npm run dev
```

Open **http://localhost:3000**.

### Python backend instead of the TS mock

```bash
# Terminal 1
npm run python:service

# Terminal 2
CL_SIM_BACKEND=python npm run dev
```

By default the Next.js routes proxy to `http://127.0.0.1:8765`. Override with `CL_SIM_PYTHON_URL` if needed.

## Tests

```bash
npm test
```

Runs Vitest (e.g. binary STIM/SPIKE round-trips in `lib/simulator/packets.test.ts`).

## API overview

### `GET /api/simulator`

Returns the current simulator snapshot, metrics, and a **`cl1`** block: last-tick 64-channel frequencies, amplitudes (µA), raw spike totals, and normalized counts.

### `POST /api/simulator/control`

Control the simulator loop.

```json
{
  "action": "start",
  "tickIntervalMs": 150,
  "neuronCount": 32
}
```

Supported `action` values: `start`, `stop`, `reset`, `tick`.

### `GET /api/simulator/device`

Returns the same last-tick **`cl1`** frame plus **base64** STIM (520 B) and SPIKE (264 B) blobs for integration tests without UDP.

### `POST /api/simulator/recording`

Mock **recording lifecycle**: capture one **JSON-serializable frame per tick** (64-ch spikes + STIM arrays) while active.

```json
{ "action": "start", "session": "my-run" }
{ "action": "stop", "persist": true }
```

With `persist: true`, frames are written under `recordings/` (gitignored). The JSON response from **stop** may include `recordingExport.savedPath`.

### `POST /api/simulator/feedback`

Typed **feedback** queue (separate from the main MEA stim UI), applied on the **next tick**: merges Hz/µA into the STIM arrays; **`interrupt`** clears pending electrode stims first.

```json
{
  "feedbackType": "reward",
  "channels": [2, 3],
  "frequencyHz": 20,
  "amplitudeUa": 0.8,
  "pulses": 1,
  "unpredictable": false,
  "eventName": "bonus"
}
```

### `POST /api/simulator/stim`

Queue stimulation on **stimulable** channels only (`1–62` except `4, 7, 56`). Dead channels return `400`.

```json
{
  "channels": [1, 2],
  "currentUa": 1.0,
  "leadTimeUs": 80,
  "burstDesign": { "burstCount": 1, "burstHz": 20 }
}
```

## Repository layout

```
app/          # Next.js App Router, page + API routes
components/   # UI
lib/simulator/# TS simulator, packets, constants
cl_sim/       # Python package (pyproject name: cl-sim)
docs/         # PRD, CL1 notes, Python simulator doc
scripts/      # CLI / protocol helpers
```
