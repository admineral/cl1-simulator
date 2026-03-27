#!/usr/bin/env python3
"""Suggest CL1 channel allocations while preserving the dead-channel mask."""

from __future__ import annotations

import argparse
import json
from typing import Dict, List

TOTAL_CHANNELS = 64
DEAD_CHANNELS = {0, 4, 7, 56, 63}
ACTIVE_CHANNELS = [idx for idx in range(TOTAL_CHANNELS) if idx not in DEAD_CHANNELS]


def allocate_layout(learned: int, positive_feedback: int, negative_feedback: int) -> Dict[str, List[int]]:
    needed = learned + positive_feedback + negative_feedback
    if needed > len(ACTIVE_CHANNELS):
        raise ValueError(
            f"Requested {needed} active channels, but only {len(ACTIVE_CHANNELS)} are available."
        )

    cursor = 0
    learned_channels = ACTIVE_CHANNELS[cursor : cursor + learned]
    cursor += learned
    positive_channels = ACTIVE_CHANNELS[cursor : cursor + positive_feedback]
    cursor += positive_feedback
    negative_channels = ACTIVE_CHANNELS[cursor : cursor + negative_feedback]
    cursor += negative_feedback
    unused_channels = ACTIVE_CHANNELS[cursor:]

    return {
        "learned_channels": learned_channels,
        "positive_feedback_channels": positive_channels,
        "negative_feedback_channels": negative_channels,
        "unused_active_channels": unused_channels,
        "dead_channels": sorted(DEAD_CHANNELS),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Suggest a CL1 channel layout")
    parser.add_argument("--learned", type=int, default=42)
    parser.add_argument("--positive-feedback", type=int, default=8)
    parser.add_argument("--negative-feedback", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    layout = allocate_layout(args.learned, args.positive_feedback, args.negative_feedback)
    if args.json:
        print(json.dumps(layout, indent=2))
        return
    for key, value in layout.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
