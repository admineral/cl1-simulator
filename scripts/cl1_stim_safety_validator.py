#!/usr/bin/env python3
"""Validate CL1 stimulation settings against documented safety bounds.

Use this script when a project needs a standalone safety check before sending
stimulation settings to a CL1 bridge or SDK.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Iterable, List

DEAD_CHANNELS = {0, 4, 7, 56, 63}
STIMMABLE_CHANNELS = {ch for ch in range(1, 63) if ch not in DEAD_CHANNELS}

MIN_AMP_UA = 0.0
MAX_AMP_UA = 3.0
PULSE_WIDTH_STEP_US = 20
MAX_PULSE_WIDTH_US = 10_000
MAX_CHARGE_NC = 3.0
NEAR_LIMIT_FRACTION = 0.9


@dataclass
class ValidationMessage:
    level: str
    message: str


def _near_limit(value: float, limit: float) -> bool:
    return limit > 0 and value >= limit * NEAR_LIMIT_FRACTION


def _docs_refresh_message() -> str:
    return "Near documented limit. Re-check https://docs.corticallabs.com/ before using this value."


def validate_channels(channels: Iterable[int]) -> List[ValidationMessage]:
    messages: List[ValidationMessage] = []
    for channel in channels:
        if channel not in STIMMABLE_CHANNELS:
            messages.append(
                ValidationMessage("error", f"Channel {channel} is not in the stimmable CL1 set.")
            )
    return messages


def validate_stim_values(amplitude_ua: float, pulse_width_us: int) -> List[ValidationMessage]:
    messages: List[ValidationMessage] = []

    if not (MIN_AMP_UA <= amplitude_ua <= MAX_AMP_UA):
        messages.append(
            ValidationMessage(
                "error",
                f"Amplitude {amplitude_ua} uA is outside the documented range [0.0, {MAX_AMP_UA}].",
            )
        )
    elif _near_limit(amplitude_ua, MAX_AMP_UA):
        messages.append(
            ValidationMessage(
                "warning",
                f"Amplitude {amplitude_ua} uA is near the documented limit {MAX_AMP_UA} uA. {_docs_refresh_message()}",
            )
        )

    if pulse_width_us <= 0 or pulse_width_us > MAX_PULSE_WIDTH_US:
        messages.append(
            ValidationMessage(
                "error",
                f"Pulse width {pulse_width_us} us is outside the documented range (0, {MAX_PULSE_WIDTH_US}].",
            )
        )
    elif pulse_width_us % PULSE_WIDTH_STEP_US != 0:
        messages.append(
            ValidationMessage(
                "error",
                f"Pulse width {pulse_width_us} us must be in {PULSE_WIDTH_STEP_US} us steps.",
            )
        )
    elif _near_limit(float(pulse_width_us), float(MAX_PULSE_WIDTH_US)):
        messages.append(
            ValidationMessage(
                "warning",
                f"Pulse width {pulse_width_us} us is near the documented limit {MAX_PULSE_WIDTH_US} us. {_docs_refresh_message()}",
            )
        )

    charge_nc = amplitude_ua * pulse_width_us / 1000.0
    if charge_nc > MAX_CHARGE_NC:
        messages.append(
            ValidationMessage(
                "error",
                f"Pulse charge {charge_nc:.3f} nC exceeds the documented limit {MAX_CHARGE_NC} nC.",
            )
        )
    elif _near_limit(charge_nc, MAX_CHARGE_NC):
        messages.append(
            ValidationMessage(
                "warning",
                f"Pulse charge {charge_nc:.3f} nC is near the documented limit {MAX_CHARGE_NC} nC. {_docs_refresh_message()}",
            )
        )

    return messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CL1 stimulation settings")
    parser.add_argument("--amplitude-ua", type=float, required=True)
    parser.add_argument("--pulse-width-us", type=int, required=True)
    parser.add_argument("--channels", type=int, nargs="*", default=[])
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of plain text")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    messages = validate_channels(args.channels)
    messages.extend(validate_stim_values(args.amplitude_ua, args.pulse_width_us))

    ok = not any(msg.level == "error" for msg in messages)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "messages": [msg.__dict__ for msg in messages],
                },
                indent=2,
            )
        )
        raise SystemExit(0 if ok else 1)

    if not messages:
        print("OK: settings are within documented bounds.")
        raise SystemExit(0)

    for msg in messages:
        print(f"{msg.level.upper()}: {msg.message}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
