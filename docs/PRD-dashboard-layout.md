# PRD: CL1 Dashboard — Layout & Visual System

## 1. Purpose

Define how the local CL1 simulator dashboard is structured so operators can **run the loop**, **queue stimulation**, **read population state**, and **annotate streams** with minimal scrolling and clear visual hierarchy—aligned with an **in-vitro / MEA lab console** metaphor (not a generic admin UI).

## 2. Goals

| Goal | Success signal |
|------|----------------|
| **Less scrolling** | Primary readouts (lattice, activity, raster) fit typical laptop viewports without excessive vertical travel. |
| **Even neuron lattice** | Grid is a **full rectangle**: column count is chosen so neuron count divides evenly when possible; no accidental “7+7+2” ragged rows. |
| **Legible controls** | Settings are grouped into labeled blocks (transport, stim, stream), with aligned label/input pairs—not one long ambiguous toolbar row. |
| **Concept clarity** | Copy and structure reinforce “dish ↔ electrodes ↔ ticks ↔ readouts,” not generic dashboard widgets. |

## 3. Non-goals

- Pixel-perfect match to any external product; this is a **local simulator** UI.
- Mobile-first polish beyond basic responsive stacking; primary target is **desktop / lab display**.

## 4. Information architecture (vertical order)

1. **Hero & telemetry** — Product framing + live badges (run state, tick, device time, channel count).
2. **Control console** — Four blocks on a **2×2 grid** (wide): transport | stim on row 1; **data stream** | **electrode queue** on row 2 (frees chart width on the main stage). Narrow screens stack in DOM order.
3. **Status line** — Single-line telemetry / errors.
4. **Main stage** (priority order):
   - **Neuron lattice** — Membrane-level grid; scroll only inside lattice if `N` is large.
   - **Visual band (`cortex-visual-band`):** **Two** columns on wide screens: **neuron lattice** (row 1, col 1) beside **population activity** (row 1, col 2); **spacer** (row 2, col 1) + **spike raster** (row 2, col 2). Electrode queue is **not** here—it lives in the console beside the data stream. Below `~1040px`: stack (spacer hidden) lattice → activity → raster.

## 5. Layout rules

### 5.1 Control console

- **Grid:** Two columns × two rows on wide screens: (transport | stimulation), then (**data stream** | **electrode queue**).
- **Per block:** Header row (mono tag + Syne title) + body with consistent vertical rhythm (`~10px` gaps).
- **Inputs:** Short numeric fields; channel list capped width; payload textarea **height-limited**, not full-bleed.

### 5.2 Neuron lattice

- **Column selection:** `latticeColumns(N)` prefers a divisor `d` of `N` (with `1 < d < N`) closest to `√N`, capped at 24. If none exist (e.g. prime `N`), fall back to `round(√N)`—last row may be short; that case is rare in typical configs.
- **Cell sizing:** Fixed cell size via CSS variable; lattice wrapper uses **max-height + internal scroll** so large `N` does not inflate the page.

### 5.3 Charts

- **Alignment:** Population activity and spike raster use a **shared outer width** (`CHART_WIDTH`) and **shared horizontal plot insets** (`CHART_INSET_X`) so the **time/plot band lines up** when panels are stacked in the same column.
- SVG viewBoxes remain fixed; CSS **max-height** scales them down so they don’t dominate vertical space.

### 5.4 Responsive

- Below `~920px`, console stacks to a single column.
- **Visual band:** Below `~1040px`, lattice and readouts stack in a single column.
- Stim key/value grid collapses to two columns on narrow widths.

## 6. Visual system

- **Background:** Deep charcoal with subtle teal/amber glow—**lab monitor**, not marketing gradient.
- **Typography:** Syne (headlines), DM Sans (UI), JetBrains Mono (telemetry, labels, values).
- **Accent:** Teal for activity / primary actions; **amber** for stimulation-linked raster marks.
- **Controls:** Raised panels with hairline borders; block headers with **left-weighted accent strip** (gradient) for scanability.

## 7. Accessibility & usability

- Transport actions exposed as `role="toolbar"` where appropriate.
- Form controls retain visible `<label>` associations (`ctl-kv` pattern).
- Errors use distinct statusline styling; don’t rely on color alone (copy includes state).

## 8. Open questions / future

- Optional **preset bar** for common `(N, Δt)` pairs.
- Collapsible **advanced stim** (custom phase design) if API surface grows.
- **Theme toggle** for light rooms (lower priority).

## 9. Change log

| Date | Change |
|------|--------|
| 2026-03-20 | Initial PRD; lattice divisor rule; console block layout documented. |
| 2026-03-20 | Readouts grid: activity + raster same column; shared `CHART_WIDTH` / `CHART_INSET_X` for aligned plots. |
| 2026-03-20 | `cortex-visual-band`: lattice left rail + stacked charts; electrode queue moved to console beside data stream; wider `CHART_WIDTH`. |
