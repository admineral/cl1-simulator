# Python CL Simulator

## Intent

This package adds a Python-first local simulator that keeps the **official Cortical Labs API mental model** at the top of the stack:

- `with cl.open() as neurons:`
- `neurons.loop()`
- `neurons.stim()`
- `neurons.create_stim_plan()`
- `neurons.record()`
- `neurons.read()`
- `neurons.timestamp()`
- `neurons.create_data_stream()`
- `interrupt()`, `interrupt_then_stim()`, and `sync()`

The API surface above is the compatibility target.

## Official-Compatible vs Project-Specific

Official-compatible behavior in this package:

- timeline-first runtime with one authoritative device timestamp
- stimulation primitives preserved as `ChannelSet`, `StimDesign`, `BurstDesign`, and `StimPlan`
- stimulation validation against the documented bounds currently captured in this repo
- loop ticks that expose frames, spikes, stims, and controller timing metadata
- raw buffered reads, streaming recording, and timestamped data streams

Project-specific conventions in this repo:

- 64-channel default synthetic layout
- dead-channel mask `(0, 4, 7, 56, 63)`
- artifact window defaults
- UDP packet schemas under [cl_sim/transport/protocol.py](/Users/eliaszobler/codexOne/cl_sim/transport/protocol.py)
- feedback/event packets under [cl_sim/transport/events.py](/Users/eliaszobler/codexOne/cl_sim/transport/events.py)
- training ablation helpers and session scaffolding under [cl_sim/training](/Users/eliaszobler/codexOne/cl_sim/training)

Use `ProjectConventionProfile` when you want those repo conventions explicitly applied. If you omit it, the API surface still works, but the runtime does not claim the dead-channel mask is an official Cortical Labs guarantee.

## Architecture

- [cl_sim/api/open.py](/Users/eliaszobler/codexOne/cl_sim/api/open.py): entrypoint and environment-backed backend selection
- [cl_sim/api/neurons.py](/Users/eliaszobler/codexOne/cl_sim/api/neurons.py): `Neurons` runtime interface
- [cl_sim/api/stim.py](/Users/eliaszobler/codexOne/cl_sim/api/stim.py): stimulation primitives and safety validation
- [cl_sim/runtime/scheduler.py](/Users/eliaszobler/codexOne/cl_sim/runtime/scheduler.py): authoritative timeline, blocking reads, queueing, recording
- [cl_sim/backends/synthetic.py](/Users/eliaszobler/codexOne/cl_sim/backends/synthetic.py): local synthetic backend with deterministic seeded behavior
- [cl_sim/backends/replay.py](/Users/eliaszobler/codexOne/cl_sim/backends/replay.py): replay backend for recorded sessions
- [cl_sim/storage/jsonl_writer.py](/Users/eliaszobler/codexOne/cl_sim/storage/jsonl_writer.py): streaming recording writer
- [cl_sim/storage/jsonl_reader.py](/Users/eliaszobler/codexOne/cl_sim/storage/jsonl_reader.py): replay loader

## Current Limitations

- This package follows the official **mental model** and documented safety limits, but it is not the official Cortical Labs SDK.
- `read()` returns a Python `FrameChunk`, not a NumPy array.
- The synthetic backend produces realistic-enough local development behavior, not biological ground truth.
- Replay mode surfaces live scheduled stim events in loop analysis, but it does not rewrite recorded frames.
- The training modules are intentionally lightweight scaffolding for ablations and closed-loop orchestration; they are not a full deep-learning framework.
