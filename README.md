# CodexOne · CL1 Simulator

Next.js-Frontend und lokale APIs für einen **CL1-orientierten MEA-Simulator**: Tick-Loops, synthetische Spike-Ausgabe, Stimulation und Recording — zum Entwickeln und Testen ohne Hardware.

Der **Dashboard-Aufbau** ist in [`docs/PRD-dashboard-layout.md`](docs/PRD-dashboard-layout.md) beschrieben.

## Was drin ist

| Teil | Beschreibung |
|------|----------------|
| **Next.js-App** | Dashboard + Route-Handler unter `app/api/simulator/*` |
| **TS-Mock** | In-Process-Simulator (`lib/simulator/`) — vom Dashboard und den APIs genutzt |
| **Python `cl_sim`** | Optionaler CL-kompatibler Dienst (`cl.open()`), siehe [`docs/python-cl-simulator.md`](docs/python-cl-simulator.md) |

### CL1-Referenz (Konzepte, nicht nur dieser Mock)

- [`docs/CL1-model-patterns.md`](docs/CL1-model-patterns.md) — Baselines, SFE, Readout-Ablations, Feedback, hardwarebewusstes Training  
- [`docs/CL1-operations-patterns.md`](docs/CL1-operations-patterns.md) — Ports, Control vs. Data Plane, Recording, Observability  
- [`docs/CL1-udp-protocol.md`](docs/CL1-udp-protocol.md) — Channel-Mask, Validierung, Beispiel-Binary-Packets, Timing  

### In-Repo CL1-Mock (TypeScript)

- [`lib/simulator/cl1-constants.ts`](lib/simulator/cl1-constants.ts) — 64 Elektroden, Dead-Channel-Mask `{0,4,7,56,63}`, 59 stimmbare IDs, Spike-Normalisierung `clamp / 35`  
- [`lib/simulator/packets.ts`](lib/simulator/packets.ts) — `packStimPacket` / `packSpikePacket` (520 B / 264 B), abgestimmt mit [`scripts/cl1_multiport_protocol_helper.py`](scripts/cl1_multiport_protocol_helper.py)  
- [`lib/simulator/core.ts`](lib/simulator/core.ts) — Tick-Loop füllt **`cl1`-Frames** (Freq/µA-Arrays + Spike-Counts); Stimulation auf Dead-Channels wird abgewiesen  

Zusätzliche **Python-Hilfs-Skripte**: [`scripts/README.md`](scripts/README.md). Menschenlesbare Referenzkopien: [`references/`](references/).

## Voraussetzungen

- **Node.js** (für `npm install` / Next 16)  
- **Python ≥ 3.10** nur für `cl_sim` / `npm run python:service`  

## Schnellstart

```bash
npm install
npm run dev
```

App: **http://localhost:3000**

### Python-Backend statt TS-Mock

```bash
# Terminal 1
npm run python:service

# Terminal 2
CL_SIM_BACKEND=python npm run dev
```

Standard-Ziel des Proxys: `http://127.0.0.1:8765` — überschreibbar mit `CL_SIM_PYTHON_URL`.

## Tests

```bash
npm test
```

Vitest (u. a. STIM/SPIKE Round-Trips in `lib/simulator/packets.test.ts`).

## API (Kurzüberblick)

### `GET /api/simulator`

Snapshot, Metriken und **`cl1`**-Block: letzter Tick — 64-Kanal-Frequenzen, Amplituden (µA), Roh-Spike-Summen, normalisierte Counts.

### `POST /api/simulator/control`

Simulator steuern.

```json
{
  "action": "start",
  "tickIntervalMs": 150,
  "neuronCount": 32
}
```

`action`: `start` · `stop` · `reset` · `tick`

### `GET /api/simulator/device`

Letzter **`cl1`**-Frame plus **base64**-STIM (520 B) und SPIKE (264 B) für Integrationstests ohne UDP.

### `POST /api/simulator/recording`

Mock-Recording: ein **JSON-serialisierbarer Frame pro Tick**.

```json
{ "action": "start", "session": "my-run" }
{ "action": "stop", "persist": true }
```

Mit `persist: true` → Dateien unter `recordings/` (gitignored). Antwort bei **stop** kann `recordingExport.savedPath` enthalten.

### `POST /api/simulator/feedback`

Feedback-Warteschlange (getrennt vom Haupt-STIM-UI), wirkt **nächster Tick**: merged Hz/µA in die STIM-Arrays; **`interrupt`** leert pending Elektroden-STIMs zuerst.

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

Nur **stimmbare** Kanäle (`1–62` außer `4, 7, 56`). Dead-Channels → `400`.

```json
{
  "channels": [1, 2],
  "currentUa": 1.0,
  "leadTimeUs": 80,
  "burstDesign": { "burstCount": 1, "burstHz": 20 }
}
```

## Projektstruktur (grob)

```
app/          # Next.js App Router, Seite + API-Routen
components/   # UI
lib/simulator/# TS-Simulator, Pakete, Konstanten
cl_sim/       # Python-Paket (pyproject: cl-sim)
docs/         # PRD, CL1-Notizen, Python-Simulator-Doku
scripts/      # CLI / Protokoll-Helfer
```
