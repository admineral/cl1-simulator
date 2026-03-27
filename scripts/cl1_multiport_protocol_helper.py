#!/usr/bin/env python3
"""Helpers for multi-port CL1 transports with stim, spike, event, and feedback messages."""

from __future__ import annotations

import json
import struct
import time
from typing import Dict, List, Sequence, Tuple

TOTAL_CHANNELS = 64
STIM_FORMAT = f"<Q{TOTAL_CHANNELS}f{TOTAL_CHANNELS}f"
SPIKE_FORMAT = f"<Q{TOTAL_CHANNELS}f"
MAX_CHANNELS_PER_FEEDBACK = 64
FEEDBACK_NAME_SIZE = 32
# timestamp_us, type, channel_count, 64 channel slots (0xFF = unused), freq_hz, amp_ua, pulses, unpredictable, event_name
FEEDBACK_FORMAT = "<QBB64BIfIB32s"

FEEDBACK_TYPE_INTERRUPT = 0
FEEDBACK_TYPE_EVENT = 1
FEEDBACK_TYPE_REWARD = 2


def now_us() -> int:
    return int(time.time() * 1_000_000)


def pack_stim(frequencies: Sequence[float], amplitudes: Sequence[float]) -> bytes:
    if len(frequencies) != TOTAL_CHANNELS or len(amplitudes) != TOTAL_CHANNELS:
        raise ValueError("stim arrays must both be length 64")
    return struct.pack(STIM_FORMAT, now_us(), *frequencies, *amplitudes)


def unpack_stim(packet: bytes) -> Tuple[int, List[float], List[float]]:
    values = struct.unpack(STIM_FORMAT, packet)
    timestamp = int(values[0])
    freqs = list(values[1 : 1 + TOTAL_CHANNELS])
    amps = list(values[1 + TOTAL_CHANNELS :])
    return timestamp, freqs, amps


def pack_spike(spike_counts: Sequence[float]) -> bytes:
    if len(spike_counts) != TOTAL_CHANNELS:
        raise ValueError("spike_counts must be length 64")
    return struct.pack(SPIKE_FORMAT, now_us(), *spike_counts)


def unpack_spike(packet: bytes) -> Tuple[int, List[float]]:
    values = struct.unpack(SPIKE_FORMAT, packet)
    return int(values[0]), list(values[1:])


def pack_event_metadata(event_type: str, data: Dict[str, object]) -> bytes:
    timestamp = now_us()
    payload = json.dumps({"timestamp": timestamp, "event_type": event_type, "data": data}).encode("utf-8")
    return struct.pack("<QI", timestamp, len(payload)) + payload


def unpack_event_metadata(packet: bytes) -> Tuple[int, str, Dict[str, object]]:
    if len(packet) < 12:
        raise ValueError("packet too small for metadata header")
    _, length = struct.unpack("<QI", packet[:12])
    payload = json.loads(packet[12 : 12 + length].decode("utf-8"))
    return int(payload["timestamp"]), str(payload["event_type"]), dict(payload["data"])


def pack_feedback_command(
    feedback_type: str,
    channels: Sequence[int],
    frequency_hz: int,
    amplitude_ua: float,
    pulses: int,
    unpredictable: bool = False,
    event_name: str = "",
) -> bytes:
    type_map = {
        "interrupt": FEEDBACK_TYPE_INTERRUPT,
        "event": FEEDBACK_TYPE_EVENT,
        "reward": FEEDBACK_TYPE_REWARD,
    }
    if feedback_type not in type_map:
        raise ValueError(f"invalid feedback type: {feedback_type}")
    if len(channels) > MAX_CHANNELS_PER_FEEDBACK:
        raise ValueError("too many channels for feedback packet")
    padded_channels = [0xFF] * MAX_CHANNELS_PER_FEEDBACK
    for index, channel in enumerate(channels):
        padded_channels[index] = int(channel)
    name_bytes = event_name.encode("utf-8")[:FEEDBACK_NAME_SIZE].ljust(FEEDBACK_NAME_SIZE, b"\x00")
    return struct.pack(
        FEEDBACK_FORMAT,
        now_us(),
        type_map[feedback_type],
        len(channels),
        *padded_channels,
        int(frequency_hz),
        float(amplitude_ua),
        int(pulses),
        1 if unpredictable else 0,
        name_bytes,
    )


def unpack_feedback_command(packet: bytes) -> Tuple[int, str, List[int], int, float, int, bool, str]:
    unpacked = struct.unpack(FEEDBACK_FORMAT, packet)
    type_map = {
        FEEDBACK_TYPE_INTERRUPT: "interrupt",
        FEEDBACK_TYPE_EVENT: "event",
        FEEDBACK_TYPE_REWARD: "reward",
    }
    count = unpacked[2]
    channels = [int(ch) for ch in unpacked[3:67][:count] if ch != 0xFF]
    return (
        int(unpacked[0]),
        type_map.get(int(unpacked[1]), "unknown"),
        channels,
        int(unpacked[67]),
        float(unpacked[68]),
        int(unpacked[69]),
        bool(unpacked[70]),
        unpacked[71].rstrip(b"\x00").decode("utf-8"),
    )


if __name__ == "__main__":
    stim = pack_stim([4.0] * TOTAL_CHANNELS, [0.0] * TOTAL_CHANNELS)
    print(len(stim), unpack_stim(stim)[0] > 0)
    spike = pack_spike([0.0] * TOTAL_CHANNELS)
    print(len(spike), unpack_spike(spike)[0] > 0)
    event = pack_event_metadata("training_complete", {"step": 42})
    print(unpack_event_metadata(event))
    feedback = pack_feedback_command("reward", [1, 2, 3], 20, 2.0, 5, event_name="reward")
    print(unpack_feedback_command(feedback))
