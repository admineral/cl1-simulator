#!/usr/bin/env python3
"""Round-trip tests for the bundled multi-port CL1 transport helpers."""

from __future__ import annotations

from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cl1_multiport_protocol_helper import (  # noqa: E402
    TOTAL_CHANNELS,
    pack_event_metadata,
    pack_feedback_command,
    pack_spike,
    pack_stim,
    unpack_event_metadata,
    unpack_feedback_command,
    unpack_spike,
    unpack_stim,
)


def main() -> None:
    stim_packet = pack_stim([4.0] * TOTAL_CHANNELS, [0.0] * TOTAL_CHANNELS)
    _, freqs, amps = unpack_stim(stim_packet)
    assert len(freqs) == TOTAL_CHANNELS
    assert len(amps) == TOTAL_CHANNELS

    spike_packet = pack_spike([1.0] * TOTAL_CHANNELS)
    _, spikes = unpack_spike(spike_packet)
    assert len(spikes) == TOTAL_CHANNELS

    event_packet = pack_event_metadata("checkpoint", {"step": 100})
    _, event_type, data = unpack_event_metadata(event_packet)
    assert event_type == "checkpoint"
    assert data["step"] == 100

    feedback_packet = pack_feedback_command(
        "reward",
        [1, 2, 3],
        20,
        2.0,
        5,
        unpredictable=True,
        event_name="reward",
    )
    (
        _ts,
        feedback_type,
        channels,
        frequency,
        amplitude,
        pulses,
        unpredictable,
        event_name,
    ) = unpack_feedback_command(feedback_packet)
    assert feedback_type == "reward"
    assert channels == [1, 2, 3]
    assert frequency == 20
    assert amplitude == 2.0
    assert pulses == 5
    assert unpredictable is True
    assert event_name == "reward"

    print("All transport self-tests passed.")


if __name__ == "__main__":
    main()
