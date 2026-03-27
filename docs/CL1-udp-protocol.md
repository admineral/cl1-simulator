# CL1 UDP Protocol

## Core invariants

- Keep `TOTAL_CHANNELS = 64`.
- Treat channels `[0, 4, 7, 56, 63]` as dead.
- Use active channels for all learned and feedback roles.
- Use the official CL API safety limits as hard bounds:
  - Amplitude: `(0.0, 3.0] uA`
  - Pulse width: `(0, 10000] us` in `20 us` steps
  - Total charge per stim pulse: `<= 3 nC`
- Use `amp = 0.0` to silence a channel. Silent channels may skip validation.

Use conservative defaults below those limits unless the task requires otherwise. If the requested values approach the upper end of the allowed range, re-check the current official docs first, then validate explicitly and call out the risk.

## Validation guidance

- Validate channel IDs against the stimmable set `1-62` excluding `0, 4, 7, 56, 63`.
- Validate amplitude against the official bound before packing or dispatching a stim.
- Validate pulse width granularity in addition to its numeric range.
- Validate pulse charge, not just amplitude. A narrow safe amplitude can still become unsafe when pulse width grows.
- If an implementation uses SDK-side config models or type aliases, prefer those validators over handwritten checks.
- If values are close to the documented limits, re-pull the official docs and validate against the current published limits instead of assuming cached values are still correct.
- Add round-trip transport tests when changing packet formats, field order, padding, or variable-length metadata.

## Channel-role guidance

- Reserve some active channels for learned stimulation.
- Reserve optional feedback channels if the training scheme uses online reinforcement or neuromodulatory cues.
- Keep channel-role boundaries explicit in code so learned stimulation, feedback, and silence are easy to reason about.

Treat the exact split as task-dependent. Preserve the dead-channel mask even if the role layout changes.

## Example packet format

Little-endian binary packets:

- `STIM`: `uint64 timestamp_us | float32[64] frequencies | float32[64] amplitudes`
- `SPIKE`: `uint64 timestamp_us | float32[64] spike_counts`

Sizes:

- `STIM_PACKET_SIZE = 520`
- `SPIKE_PACKET_SIZE = 264`

This is one proven schema, not a requirement for every CL1 project.

General rule:

- Define the transport schema explicitly.
- Keep sender and receiver aligned on field order, sizes, and timing semantics.
- Do not change one side of the bridge without updating the other.

## Additional packet types

Stim and spike packets are only part of a larger CL1 transport design.

Useful additional packet types:

- event metadata packets for lifecycle and run state
- feedback packets for reward, event, or interrupt stimulation
- health or heartbeat packets when long-running distributed systems need explicit liveness checks

These packets can use a different schema and a different port from the main stim/spike path.

## Training-side timing

- Wait `50 ms` after transmit before accepting spikes: `SPIKE_ARTIFACT_WAIT_S = 0.050`
- Fail a receive after `5 s`: `UDP_TIMEOUT_S = 5.0`
- Retry timed-out stim rounds up to a small bounded count. `3` attempts is a reasonable starting point.

These values matter because CL1 is not a regular RPC service. Spike windows contain stimulation artifacts, and occasional packet or device delays are normal.

## Device-side timing

A typical device bridge loop on the CL1 side uses:

- `tick_rate = 1000 Hz` by default
- `ARTIFACT_TICKS = 10`
- `COLLECT_TICKS = 50`
- `PHASE_WIDTH_US = 200`

The device path is:

1. Receive a full 520-byte stim packet.
2. Parse 64 frequencies and 64 amplitudes.
3. Build one batched stimulation plan with the CL SDK.
4. Ignore spikes during the artifact window.
5. Count spikes during the collection window.
6. Reply with one 264-byte spike packet.

## Practical guidance

- Keep the training client non-blocking or async.
- Disable Windows UDP connection reset noise when using Python sockets if available.
- Keep dead-channel spike counts zeroed before downstream normalization.
- Normalize only active-channel spike counts on the model side.
- Preserve packet timestamps even if you do not use them for routing; they are useful for latency inspection and debugging.
- If CL1 handling is unclear, defer to the official docs first: [Cortical Labs documentation](https://docs.corticallabs.com/).
