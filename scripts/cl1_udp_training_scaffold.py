#!/usr/bin/env python3
"""Reusable scaffold for CL1-compatible UDP training loops.

This script is intentionally minimal and self-contained. Use it as a starting
point when a project needs:

- CL1 packet packing/unpacking
- Channel-role mapping into 64-channel stim arrays
- Safe stimulation validation
- Async UDP request/response handling
- Mandatory rest-cycle enforcement

Implement `TrainingHooks` for the actual model-specific logic.
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import struct
import time
from dataclasses import dataclass
from typing import List, Protocol, Sequence, Tuple

TOTAL_CHANNELS = 64
DEAD_CHANNELS = [0, 4, 7, 56, 63]
ACTIVE_CHANNELS = [idx for idx in range(TOTAL_CHANNELS) if idx not in set(DEAD_CHANNELS)]

ENCODER_CHANNEL_COUNT = 42
POS_FEEDBACK_COUNT = 8
NEG_FEEDBACK_COUNT = 8

MIN_FREQ_HZ = 4.0
MAX_FREQ_HZ = 40.0
MIN_AMP_UA = 1.0
MAX_AMP_UA = 3.0

PULSE_WIDTH_STEP_US = 20
MAX_PULSE_WIDTH_US = 10_000
MAX_CHARGE_NC = 3.0
DEFAULT_PULSE_WIDTH_US = 200
NEAR_LIMIT_FRACTION = 0.9

# Wait before accepting spikes to avoid stimulation artifacts contaminating reads.
SPIKE_ARTIFACT_WAIT_S = 0.050
UDP_TIMEOUT_S = 5.0

MAX_TRAIN_SECONDS = int(2.5 * 3600)
REST_SECONDS = int(1.0 * 3600)

STIM_FORMAT = f"<Q{TOTAL_CHANNELS}f{TOTAL_CHANNELS}f"
SPIKE_FORMAT = f"<Q{TOTAL_CHANNELS}f"
STIM_PACKET_SIZE = struct.calcsize(STIM_FORMAT)
SPIKE_PACKET_SIZE = struct.calcsize(SPIKE_FORMAT)


def now_us() -> int:
    return int(time.time() * 1_000_000)


def _warn_if_near_limit(label: str, value: float, limit: float) -> None:
    if limit <= 0:
        return
    if value >= limit * NEAR_LIMIT_FRACTION:
        print(f"Warning: {label}={value} is near the documented limit {limit}.")


def validate_stim(
    frequencies: Sequence[float],
    amplitudes: Sequence[float],
    pulse_width_us: int = DEFAULT_PULSE_WIDTH_US,
) -> None:
    if len(frequencies) != TOTAL_CHANNELS:
        raise ValueError(f"Expected {TOTAL_CHANNELS} frequencies, got {len(frequencies)}")
    if len(amplitudes) != TOTAL_CHANNELS:
        raise ValueError(f"Expected {TOTAL_CHANNELS} amplitudes, got {len(amplitudes)}")
    if pulse_width_us <= 0 or pulse_width_us > MAX_PULSE_WIDTH_US:
        raise ValueError(f"Pulse width {pulse_width_us} outside documented limit")
    if pulse_width_us % PULSE_WIDTH_STEP_US != 0:
        raise ValueError(f"Pulse width {pulse_width_us} must be in {PULSE_WIDTH_STEP_US} us steps")

    _warn_if_near_limit("pulse_width_us", float(pulse_width_us), float(MAX_PULSE_WIDTH_US))

    dead = set(DEAD_CHANNELS)
    for channel, (freq_hz, amp_ua) in enumerate(zip(frequencies, amplitudes)):
        if channel in dead or amp_ua == 0.0:
            continue
        if not (MIN_FREQ_HZ <= freq_hz <= MAX_FREQ_HZ):
            raise ValueError(f"Channel {channel}: freq {freq_hz} outside safe range")
        if not (MIN_AMP_UA <= amp_ua <= MAX_AMP_UA):
            raise ValueError(f"Channel {channel}: amp {amp_ua} outside safe range")
        charge_nc = amp_ua * pulse_width_us / 1000.0
        if charge_nc > MAX_CHARGE_NC:
            raise ValueError(f"Channel {channel}: charge {charge_nc:.3f} nC exceeds documented limit")
        _warn_if_near_limit(f"channel_{channel}_amp_ua", float(amp_ua), MAX_AMP_UA)
        _warn_if_near_limit(f"channel_{channel}_charge_nc", charge_nc, MAX_CHARGE_NC)


def pack_stim(
    frequencies: Sequence[float],
    amplitudes: Sequence[float],
    pulse_width_us: int = DEFAULT_PULSE_WIDTH_US,
) -> bytes:
    validate_stim(frequencies, amplitudes, pulse_width_us=pulse_width_us)
    return struct.pack(STIM_FORMAT, now_us(), *frequencies, *amplitudes)


def unpack_spike(packet: bytes) -> Tuple[int, List[float]]:
    if len(packet) != SPIKE_PACKET_SIZE:
        raise ValueError(f"Expected {SPIKE_PACKET_SIZE} bytes, got {len(packet)}")
    values = struct.unpack(SPIKE_FORMAT, packet)
    return int(values[0]), list(values[1:])


def build_stim_arrays(
    encoder_channels: Sequence[int],
    encoder_freqs: Sequence[float],
    encoder_amps: Sequence[float],
    pos_feedback_freqs: Sequence[float],
    pos_feedback_amps: Sequence[float],
    neg_feedback_freqs: Sequence[float],
    neg_feedback_amps: Sequence[float],
) -> Tuple[List[float], List[float]]:
    if len(encoder_channels) != len(encoder_freqs) or len(encoder_channels) != len(encoder_amps):
        raise ValueError("Encoder channel and stim lengths must match")

    pos_feedback_channels = ACTIVE_CHANNELS[
        ENCODER_CHANNEL_COUNT : ENCODER_CHANNEL_COUNT + POS_FEEDBACK_COUNT
    ]
    neg_feedback_channels = ACTIVE_CHANNELS[
        ENCODER_CHANNEL_COUNT
        + POS_FEEDBACK_COUNT : ENCODER_CHANNEL_COUNT
        + POS_FEEDBACK_COUNT
        + NEG_FEEDBACK_COUNT
    ]

    freqs = [MIN_FREQ_HZ] * TOTAL_CHANNELS
    amps = [0.0] * TOTAL_CHANNELS

    for idx, channel in enumerate(encoder_channels):
        freqs[channel] = float(encoder_freqs[idx])
        amps[channel] = float(encoder_amps[idx])
    for idx, channel in enumerate(pos_feedback_channels):
        freqs[channel] = float(pos_feedback_freqs[idx])
        amps[channel] = float(pos_feedback_amps[idx])
    for idx, channel in enumerate(neg_feedback_channels):
        freqs[channel] = float(neg_feedback_freqs[idx])
        amps[channel] = float(neg_feedback_amps[idx])

    return freqs, amps


@dataclass
class UdpConfig:
    cl1_host: str = "127.0.0.1"
    stim_port: int = 12345
    listen_host: str = "0.0.0.0"
    spike_port: int = 12346


class SessionManager:
    def __init__(self) -> None:
        self._segment_start = time.monotonic()

    async def rest_if_needed(self) -> None:
        if time.monotonic() - self._segment_start < MAX_TRAIN_SECONDS:
            return
        await asyncio.sleep(REST_SECONDS)
        self._segment_start = time.monotonic()


class CL1UdpClient:
    def __init__(self, config: UdpConfig, pulse_width_us: int = DEFAULT_PULSE_WIDTH_US):
        self._stim_addr = (config.cl1_host, config.stim_port)
        self._listen_addr = (config.listen_host, config.spike_port)
        self._pulse_width_us = pulse_width_us
        self._sock: socket.socket | None = None

    async def __aenter__(self) -> "CL1UdpClient":
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(self._listen_addr)
        self._sock.setblocking(False)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            try:
                self._sock.ioctl(socket.SIO_UDP_CONNRESET, False)  # type: ignore[attr-defined]
            except OSError:
                pass
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    async def stimulate(self, frequencies: Sequence[float], amplitudes: Sequence[float]) -> List[float]:
        if self._sock is None:
            raise RuntimeError("Use CL1UdpClient inside an async context manager")
        self._sock.sendto(
            pack_stim(frequencies, amplitudes, pulse_width_us=self._pulse_width_us),
            self._stim_addr,
        )
        await asyncio.sleep(SPIKE_ARTIFACT_WAIT_S)
        loop = asyncio.get_running_loop()
        packet, _ = await asyncio.wait_for(
            loop.sock_recvfrom(self._sock, SPIKE_PACKET_SIZE),
            timeout=UDP_TIMEOUT_S,
        )
        _, spike_counts = unpack_spike(packet)
        return spike_counts


class TrainingHooks(Protocol):
    def next_encoder_stim(self) -> Tuple[Sequence[int], Sequence[float], Sequence[float]]:
        """Return encoder channels, frequencies, and amplitudes for the next step."""

    def next_feedback_stim(
        self,
    ) -> Tuple[Sequence[float], Sequence[float], Sequence[float], Sequence[float]]:
        """Return positive and negative feedback arrays for the next step."""

    def handle_spikes(self, spike_counts: Sequence[float]) -> None:
        """Consume one spike packet and update task-specific training state."""


async def run_training_loop(
    hooks: TrainingHooks,
    udp_config: UdpConfig,
    steps: int,
    pulse_width_us: int = DEFAULT_PULSE_WIDTH_US,
) -> None:
    session = SessionManager()
    async with CL1UdpClient(udp_config, pulse_width_us=pulse_width_us) as client:
        for _ in range(steps):
            await session.rest_if_needed()
            channels, enc_freqs, enc_amps = hooks.next_encoder_stim()
            pos_freqs, pos_amps, neg_freqs, neg_amps = hooks.next_feedback_stim()
            all_freqs, all_amps = build_stim_arrays(
                channels,
                enc_freqs,
                enc_amps,
                pos_freqs,
                pos_amps,
                neg_freqs,
                neg_amps,
            )
            spikes = await client.stimulate(all_freqs, all_amps)
            hooks.handle_spikes(spikes)


class DemoHooks:
    def next_encoder_stim(self) -> Tuple[Sequence[int], Sequence[float], Sequence[float]]:
        channels = ACTIVE_CHANNELS[:ENCODER_CHANNEL_COUNT]
        freqs = [MIN_FREQ_HZ] * len(channels)
        amps = [MIN_AMP_UA] * len(channels)
        return channels, freqs, amps

    def next_feedback_stim(
        self,
    ) -> Tuple[Sequence[float], Sequence[float], Sequence[float], Sequence[float]]:
        pos_freqs = [MIN_FREQ_HZ] * POS_FEEDBACK_COUNT
        pos_amps = [MIN_AMP_UA] * POS_FEEDBACK_COUNT
        neg_freqs = [MIN_FREQ_HZ] * NEG_FEEDBACK_COUNT
        neg_amps = [MIN_AMP_UA] * NEG_FEEDBACK_COUNT
        return pos_freqs, pos_amps, neg_freqs, neg_amps

    def handle_spikes(self, spike_counts: Sequence[float]) -> None:
        active_mean = sum(spike_counts[idx] for idx in ACTIVE_CHANNELS) / len(ACTIVE_CHANNELS)
        print(f"Received spike packet. Active-channel mean: {active_mean:.3f}")


def run_self_test() -> None:
    encoder_channels = ACTIVE_CHANNELS[:ENCODER_CHANNEL_COUNT]
    freqs, amps = build_stim_arrays(
        encoder_channels,
        [MIN_FREQ_HZ] * len(encoder_channels),
        [MIN_AMP_UA] * len(encoder_channels),
        [MIN_FREQ_HZ] * POS_FEEDBACK_COUNT,
        [MIN_AMP_UA] * POS_FEEDBACK_COUNT,
        [MIN_FREQ_HZ] * NEG_FEEDBACK_COUNT,
        [MIN_AMP_UA] * NEG_FEEDBACK_COUNT,
    )
    payload = pack_stim(freqs, amps, pulse_width_us=DEFAULT_PULSE_WIDTH_US)
    if len(payload) != STIM_PACKET_SIZE:
        raise SystemExit("Stim packet size mismatch")
    fake_spike_packet = struct.pack(SPIKE_FORMAT, now_us(), *([0.0] * TOTAL_CHANNELS))
    _, spikes = unpack_spike(fake_spike_packet)
    if len(spikes) != TOTAL_CHANNELS:
        raise SystemExit("Spike packet size mismatch")
    print("Self-test passed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CL1 UDP training scaffold")
    parser.add_argument("--cl1-host", default="127.0.0.1")
    parser.add_argument("--stim-port", type=int, default=12345)
    parser.add_argument("--spike-port", type=int, default=12346)
    parser.add_argument("--pulse-width-us", type=int, default=DEFAULT_PULSE_WIDTH_US)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return
    config = UdpConfig(cl1_host=args.cl1_host, stim_port=args.stim_port, spike_port=args.spike_port)
    await run_training_loop(
        DemoHooks(),
        config,
        args.steps,
        pulse_width_us=args.pulse_width_us,
    )


if __name__ == "__main__":
    asyncio.run(main())
