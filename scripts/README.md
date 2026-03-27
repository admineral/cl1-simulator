# CL1 helper scripts

Small, standalone Python utilities (offline validation / protocol experiments). They do not depend on the Next.js app; the **browser mock** lives in [`lib/simulator/`](../lib/simulator/).

Run from repo root (or `cd scripts` and invoke by filename). Python 3.10+ recommended.

| Script | Purpose |
|--------|---------|
| `cl1_channel_layout_helper.py` | Propose learned / feedback channel splits honoring dead channels |
| `cl1_feedback_scaling_helper.py` | Reward / EMA-surprise scaling helpers (import as library) |
| `cl1_multiport_protocol_helper.py` | Pack/unpack STIM, SPIKE, event JSON, feedback binary |
| `cl1_stim_cache.py` | Generic LRU cache for stim design reuse |
| `cl1_stim_safety_validator.py` | CLI: validate µA, pulse width, charge, channels vs docs |
| `cl1_transport_self_test.py` | Assert round-trips for multiport helpers |
| `cl1_udp_training_scaffold.py` | Async UDP stim/spike loop template + `--self-test` |

Examples:

```bash
python3 scripts/cl1_transport_self_test.py
python3 scripts/cl1_udp_training_scaffold.py --self-test
python3 scripts/cl1_stim_safety_validator.py --amplitude-ua 1.5 --pulse-width-us 200 --channels 1 2
python3 scripts/cl1_channel_layout_helper.py --learned 42 --positive-feedback 8 --negative-feedback 8 --json
```
