from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Sequence


MIN_LEAD_TIME_US = 80
LEAD_TIME_STEP_US = 40
PULSE_DURATION_STEP_US = 20
MAX_CURRENT_UA = 3.0
MAX_CHARGE_NC = 3.0
MAX_BURST_HZ = 200
NEAR_LIMIT_FRACTION = 0.9


class StimValidationError(ValueError):
    pass


def _docs_refresh_message() -> str:
    return (
        "Value is near the currently documented limit. Re-check the latest official Cortical "
        "Labs documentation before dispatching to a bridge or device."
    )


def _normalize_channel_values(values: Sequence[int] | Iterable[int] | int) -> tuple[int, ...]:
    if isinstance(values, int):
        normalized = (values,)
    else:
        normalized = tuple(int(value) for value in values)
    if not normalized:
        raise StimValidationError("ChannelSet must contain at least one channel.")
    unique = tuple(dict.fromkeys(normalized))
    return unique


@dataclass(frozen=True, slots=True)
class ChannelSet:
    channels: tuple[int, ...]

    def __init__(self, *channels: int | Iterable[int]) -> None:
        if len(channels) == 1 and not isinstance(channels[0], int):
            object.__setattr__(self, "channels", _normalize_channel_values(channels[0]))
            return
        object.__setattr__(self, "channels", _normalize_channel_values(channels))  # type: ignore[arg-type]

    def __iter__(self) -> Iterator[int]:
        return iter(self.channels)

    def __len__(self) -> int:
        return len(self.channels)


@dataclass(frozen=True, slots=True)
class StimPhase:
    duration_us: int
    current_ua: float


@dataclass(frozen=True, slots=True)
class StimDesign:
    phases: tuple[StimPhase, ...]

    def __init__(self, *phase_args: float | int | StimPhase) -> None:
        if len(phase_args) == 1 and isinstance(phase_args[0], StimDesign):
            object.__setattr__(self, "phases", phase_args[0].phases)
            return

        if phase_args and all(isinstance(arg, StimPhase) for arg in phase_args):
            object.__setattr__(self, "phases", tuple(phase_args))  # type: ignore[arg-type]
            return

        if len(phase_args) not in (2, 4, 6):
            raise StimValidationError(
                "StimDesign expects 2, 4, or 6 scalar arguments representing 1-3 "
                "(duration_us, current_ua) pairs."
            )

        phases = []
        for index in range(0, len(phase_args), 2):
            duration_us = int(phase_args[index])
            current_ua = float(phase_args[index + 1])
            phases.append(StimPhase(duration_us=duration_us, current_ua=current_ua))
        object.__setattr__(self, "phases", tuple(phases))

    @classmethod
    def from_scalar_current(cls, value_ua: float) -> "StimDesign":
        amplitude = abs(float(value_ua))
        return cls(160, -amplitude, 160, amplitude)


@dataclass(frozen=True, slots=True)
class BurstDesign:
    burst_count: int = 1
    burst_hz: int = 0


@dataclass(frozen=True, slots=True)
class StimOperation:
    channels: ChannelSet
    design: StimDesign
    burst: BurstDesign
    lead_time_us: int
    warnings: tuple[str, ...] = ()


def coerce_stim_design(value: StimDesign | float | int) -> StimDesign:
    if isinstance(value, StimDesign):
        return value
    return StimDesign.from_scalar_current(float(value))


def validate_stim_operation(
    operation: StimOperation,
    *,
    channel_count: int,
    blocked_channels: set[int] | None = None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    blocked = blocked_channels or set()
    max_abs_current = max(abs(phase.current_ua) for phase in operation.design.phases)
    silent_operation = max_abs_current == 0.0

    for channel in operation.channels:
        if channel < 0 or channel >= channel_count:
            raise StimValidationError(
                f"Channel {channel} is out of range for the configured channel count {channel_count}."
            )
        if channel in blocked and not silent_operation:
            raise StimValidationError(
                f"Channel {channel} is blocked by the active project convention profile."
            )

    if operation.lead_time_us < MIN_LEAD_TIME_US or operation.lead_time_us % LEAD_TIME_STEP_US != 0:
        raise StimValidationError(
            f"lead_time_us must be at least {MIN_LEAD_TIME_US} and divisible by {LEAD_TIME_STEP_US}."
        )

    if operation.burst.burst_count <= 0:
        raise StimValidationError("BurstDesign.burst_count must be a positive integer.")

    if operation.burst.burst_hz > MAX_BURST_HZ:
        raise StimValidationError(f"BurstDesign.burst_hz must not exceed {MAX_BURST_HZ}.")

    if operation.burst.burst_count > 1 and operation.burst.burst_hz <= 0:
        raise StimValidationError("BurstDesign.burst_hz must be positive when burst_count > 1.")

    if operation.burst.burst_hz >= MAX_BURST_HZ * NEAR_LIMIT_FRACTION:
        warnings.append(
            f"burst_hz={operation.burst.burst_hz} is near the documented limit {MAX_BURST_HZ}. "
            f"{_docs_refresh_message()}"
        )

    previous_nonzero_sign = 0
    for index, phase in enumerate(operation.design.phases, start=1):
        if phase.duration_us <= 0 or phase.duration_us % PULSE_DURATION_STEP_US != 0:
            raise StimValidationError(
                f"Phase {index} duration must be positive and divisible by {PULSE_DURATION_STEP_US} us."
            )
        if abs(phase.current_ua) > MAX_CURRENT_UA:
            raise StimValidationError(
                f"Phase {index} current must be within {-MAX_CURRENT_UA} to {MAX_CURRENT_UA} uA."
            )

        charge_nc = abs(phase.current_ua) * phase.duration_us / 1000.0
        if charge_nc > MAX_CHARGE_NC:
            raise StimValidationError(
                f"Phase {index} exceeds the documented {MAX_CHARGE_NC} nC charge limit."
            )

        if abs(phase.current_ua) >= MAX_CURRENT_UA * NEAR_LIMIT_FRACTION:
            warnings.append(
                f"phase_{index}_current_ua={phase.current_ua:.3f} is near the documented limit "
                f"{MAX_CURRENT_UA}. {_docs_refresh_message()}"
            )
        if charge_nc >= MAX_CHARGE_NC * NEAR_LIMIT_FRACTION:
            warnings.append(
                f"phase_{index}_charge_nc={charge_nc:.3f} is near the documented limit "
                f"{MAX_CHARGE_NC}. {_docs_refresh_message()}"
            )

        current_sign = 0 if phase.current_ua == 0 else int(math.copysign(1, phase.current_ua))
        if current_sign != 0:
            if previous_nonzero_sign == current_sign:
                raise StimValidationError("Adjacent non-zero phases must alternate polarity.")
            previous_nonzero_sign = current_sign

    return tuple(warnings)


class StimPlan:
    def __init__(
        self,
        executor: Callable[[tuple[StimOperation, ...]], tuple[object, ...]],
    ) -> None:
        self._executor = executor
        self._operations: list[StimOperation] = []
        self._frozen = False

    @property
    def frozen(self) -> bool:
        return self._frozen

    @property
    def operations(self) -> tuple[StimOperation, ...]:
        return tuple(self._operations)

    def add_stim(
        self,
        channels: int | ChannelSet | Sequence[int],
        design: StimDesign | float | int,
        burst: BurstDesign | None = None,
        *,
        lead_time_us: int = MIN_LEAD_TIME_US,
    ) -> "StimPlan":
        if self._frozen:
            raise RuntimeError("StimPlan cannot be mutated after first execution.")
        channel_set = channels if isinstance(channels, ChannelSet) else ChannelSet(channels)
        operation = StimOperation(
            channels=channel_set,
            design=coerce_stim_design(design),
            burst=burst or BurstDesign(),
            lead_time_us=lead_time_us,
        )
        self._operations.append(operation)
        return self

    def execute(self) -> tuple[object, ...]:
        self._frozen = True
        return self._executor(tuple(self._operations))
