from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Mapping, Sequence


MAX_CHANNELS_PER_FEEDBACK = 64
FEEDBACK_NAME_SIZE = 32
FEEDBACK_FORMAT = "<QBB64BIfIB32s"

FEEDBACK_TYPE_INTERRUPT = 0
FEEDBACK_TYPE_EVENT = 1
FEEDBACK_TYPE_REWARD = 2


@dataclass(frozen=True, slots=True)
class FeedbackPacket:
    timestamp_us: int
    feedback_type: str
    channels: tuple[int, ...]
    frequency_hz: int
    amplitude_ua: float
    pulses: int
    unpredictable: bool
    event_name: str = ""


def pack_event_metadata(timestamp_us: int, event_type: str, data: Mapping[str, object]) -> bytes:
    payload = json.dumps(
        {"timestamp_us": timestamp_us, "event_type": event_type, "data": dict(data)},
        sort_keys=True,
    ).encode("utf-8")
    return struct.pack("<QI", timestamp_us, len(payload)) + payload


def unpack_event_metadata(packet: bytes) -> tuple[int, str, Mapping[str, object]]:
    if len(packet) < 12:
        raise ValueError("Metadata packet is too small.")
    timestamp_us, payload_size = struct.unpack("<QI", packet[:12])
    payload = json.loads(packet[12 : 12 + payload_size].decode("utf-8"))
    return int(timestamp_us), str(payload["event_type"]), dict(payload["data"])


def pack_feedback_packet(packet: FeedbackPacket) -> bytes:
    type_map = {
        "interrupt": FEEDBACK_TYPE_INTERRUPT,
        "event": FEEDBACK_TYPE_EVENT,
        "reward": FEEDBACK_TYPE_REWARD,
    }
    if packet.feedback_type not in type_map:
        raise ValueError(f"Unsupported feedback type: {packet.feedback_type}")
    if len(packet.channels) > MAX_CHANNELS_PER_FEEDBACK:
        raise ValueError("Too many channels for one feedback packet.")
    padded_channels = [0xFF] * MAX_CHANNELS_PER_FEEDBACK
    for index, channel in enumerate(packet.channels):
        padded_channels[index] = int(channel)
    name_bytes = packet.event_name.encode("utf-8")[:FEEDBACK_NAME_SIZE].ljust(
        FEEDBACK_NAME_SIZE,
        b"\x00",
    )
    return struct.pack(
        FEEDBACK_FORMAT,
        packet.timestamp_us,
        type_map[packet.feedback_type],
        len(packet.channels),
        *padded_channels,
        packet.frequency_hz,
        packet.amplitude_ua,
        packet.pulses,
        1 if packet.unpredictable else 0,
        name_bytes,
    )


def unpack_feedback_packet(packet: bytes) -> FeedbackPacket:
    unpacked = struct.unpack(FEEDBACK_FORMAT, packet)
    reverse_map = {
        FEEDBACK_TYPE_INTERRUPT: "interrupt",
        FEEDBACK_TYPE_EVENT: "event",
        FEEDBACK_TYPE_REWARD: "reward",
    }
    count = int(unpacked[2])
    channels = tuple(int(ch) for ch in unpacked[3:67][:count] if ch != 0xFF)
    return FeedbackPacket(
        timestamp_us=int(unpacked[0]),
        feedback_type=reverse_map[int(unpacked[1])],
        channels=channels,
        frequency_hz=int(unpacked[67]),
        amplitude_ua=float(unpacked[68]),
        pulses=int(unpacked[69]),
        unpredictable=bool(unpacked[70]),
        event_name=unpacked[71].rstrip(b"\x00").decode("utf-8"),
    )
