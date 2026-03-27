# CL1 Operations Patterns

## Multi-port architecture

For larger CL1 systems, separate the transport into explicit lanes instead of forcing every message through the same stim path.

Common split:

- stim commands
- spike responses
- feedback commands
- event metadata

Benefits:

- keeps the data plane simple
- allows typed control messages without overloading stim packets
- makes debugging easier because each port has one job
- lets feedback or lifecycle signaling evolve without breaking the main stim/spike path

If a project does not need multiple ports, a single-port or dual-port schema is still valid. The important part is to keep the schema explicit and synchronized between sender and receiver.

## Control plane vs data plane

Treat high-rate stimulation and spike traffic as the data plane. Treat lifecycle and coordination messages as the control plane.

Useful control-plane messages include:

- training started
- episode ended
- checkpoint saved
- training complete
- interrupt or clear-current-stim
- recording started or stopped

Metadata packets are often better as length-prefixed JSON or another self-describing format instead of ad hoc binary reuse.

## Feedback routing patterns

Do not assume feedback must share the stim transport.

Valid patterns:

- pack feedback into the next stim message
- send typed feedback packets over a separate port
- send interrupt packets separately from reward or event feedback

Treat positive, negative, reward, event, and interrupt feedback as separate semantics even if they eventually map onto the same hardware channels.

## Recording lifecycle

Document how recordings start, stop, and get named.

Good defaults:

- create the recording directory before opening the CL1 session
- start recording once the interface is fully initialized
- stop recording on explicit completion events, not only process exit
- handle double-stop and failed-stop paths safely
- store enough metadata to connect recordings back to a run or checkpoint

Recording should be part of the lifecycle design, not an afterthought.

## Startup and shutdown order

Startup order matters in distributed CL1 systems.

Strong pattern:

1. start the CL1 interface first
2. verify ports and recording paths
3. start the training or control process
4. send an explicit completion event on shutdown
5. stop recording gracefully

This reduces lost packets, stale state, and partial recordings.

## Observability

Provide at least one low-friction way to observe the system remotely.

Useful options:

- lightweight MJPEG or image streaming for state previews
- packet counters and latency logs
- spike count summaries
- feedback event logs
- periodic cache or resource stats

The goal is not a perfect dashboard. The goal is to make failures and stale state visible quickly.

## Stimulation design caching

Cache stimulation designs when the same frequency, amplitude, pulse, or channel patterns repeat.

Benefits:

- reduces repeated SDK object construction
- lowers per-step overhead
- keeps hot paths simpler once the cache key is defined

Requirements:

- make cache keys explicit and deterministic
- provide a clear cache flush path
- clear caches on shutdown or after large configuration changes

## Transport self-tests

Round-trip tests should exist for every transport schema.

Minimum coverage:

- pack then unpack each packet type
- verify field order and packet sizes
- verify padding and variable-length handling
- verify timestamp and metadata parsing

Run these tests before changing sender or receiver implementations.
