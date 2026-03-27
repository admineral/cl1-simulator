from __future__ import annotations

import struct
from typing import Sequence


TOTAL_CHANNELS = 64
STIM_FORMAT = f"<Q{TOTAL_CHANNELS}f{TOTAL_CHANNELS}f"
SPIKE_FORMAT = f"<Q{TOTAL_CHANNELS}f"
STIM_PACKET_SIZE = struct.calcsize(STIM_FORMAT)
SPIKE_PACKET_SIZE = struct.calcsize(SPIKE_FORMAT)


def pack_stim_packet(
    timestamp_us: int,
    frequencies: Sequence[float],
    amplitudes: Sequence[float],
) -> bytes:
    """Pack the repo's project-specific 64-channel UDP stim packet."""

    if len(frequencies) != TOTAL_CHANNELS or len(amplitudes) != TOTAL_CHANNELS:
        raise ValueError("Project stim packets require 64 frequencies and 64 amplitudes.")
    return struct.pack(STIM_FORMAT, timestamp_us, *frequencies, *amplitudes)


def unpack_stim_packet(packet: bytes) -> tuple[int, tuple[float, ...], tuple[float, ...]]:
    if len(packet) != STIM_PACKET_SIZE:
        raise ValueError(f"Expected {STIM_PACKET_SIZE} bytes, got {len(packet)}.")
    unpacked = struct.unpack(STIM_FORMAT, packet)
    return (
        int(unpacked[0]),
        tuple(float(value) for value in unpacked[1 : 1 + TOTAL_CHANNELS]),
        tuple(float(value) for value in unpacked[1 + TOTAL_CHANNELS :]),
    )


def pack_spike_packet(timestamp_us: int, spike_counts: Sequence[float]) -> bytes:
    if len(spike_counts) != TOTAL_CHANNELS:
        raise ValueError("Project spike packets require 64 spike counts.")
    return struct.pack(SPIKE_FORMAT, timestamp_us, *spike_counts)


def unpack_spike_packet(packet: bytes) -> tuple[int, tuple[float, ...]]:
    if len(packet) != SPIKE_PACKET_SIZE:
        raise ValueError(f"Expected {SPIKE_PACKET_SIZE} bytes, got {len(packet)}.")
    unpacked = struct.unpack(SPIKE_FORMAT, packet)
    return int(unpacked[0]), tuple(float(value) for value in unpacked[1:])
