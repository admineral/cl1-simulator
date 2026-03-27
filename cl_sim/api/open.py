from __future__ import annotations

import os

from cl_sim.api.neurons import Neurons
from cl_sim.api.types import ProjectConventionProfile
from cl_sim.backends.base import ReplayBackendConfig, SyntheticBackendConfig
from cl_sim.backends.replay import ReplayBackend
from cl_sim.backends.synthetic import SyntheticBackend
from cl_sim.runtime.clock import ClockConfig
from cl_sim.runtime.scheduler import RuntimeEngine


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None else float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None else int(raw)


def open(
    *,
    replay_path: str | None = None,
    clock_mode: str | None = None,
    accelerated_factor: float | None = None,
    loop_interval_us: int | None = None,
    synthetic_sample_mean: float | None = None,
    synthetic_spike_rate_hz: float | None = None,
    project_conventions: ProjectConventionProfile | None = None,
) -> Neurons:
    """Open a CL-compatible local simulator runtime.

    The top-level API shape follows the official Cortical Labs Python mental model.
    Backend selection, replay-path wiring, and project convention profiles are local
    simulator features layered on top of that API surface.
    """

    replay_path = replay_path or os.getenv("CL_SIM_REPLAY_PATH")
    resolved_mode = clock_mode or os.getenv("CL_SIM_CLOCK_MODE")
    if resolved_mode is None:
        resolved_mode = "replay" if replay_path else "simulated"

    resolved_acceleration = (
        accelerated_factor
        if accelerated_factor is not None
        else _env_float("CL_SIM_ACCELERATED_FACTOR", 1.0)
    )
    resolved_loop_interval_us = (
        loop_interval_us if loop_interval_us is not None else _env_int("CL_SIM_LOOP_INTERVAL_US", 10_000)
    )

    if replay_path:
        backend = ReplayBackend.from_path(ReplayBackendConfig(path=replay_path))
    else:
        backend = SyntheticBackend(
            SyntheticBackendConfig(
                channel_count=(
                    project_conventions.channel_count
                    if project_conventions is not None
                    else _env_int("CL_SIM_CHANNEL_COUNT", 64)
                ),
                sample_mean=(
                    synthetic_sample_mean
                    if synthetic_sample_mean is not None
                    else _env_float("CL_SIM_SYNTHETIC_SAMPLE_MEAN", 0.0)
                ),
                spontaneous_spike_rate_hz=(
                    synthetic_spike_rate_hz
                    if synthetic_spike_rate_hz is not None
                    else _env_float("CL_SIM_SPIKE_RATE_HZ", 2.0)
                ),
                sample_rate_hz=_env_int("CL_SIM_SAMPLE_RATE_HZ", 1_000),
                seed=_env_int("CL_SIM_RANDOM_SEED", 7),
            )
        )

    engine = RuntimeEngine(
        backend=backend,
        clock=ClockConfig(mode=resolved_mode, accelerated_factor=resolved_acceleration),
        loop_interval_us=resolved_loop_interval_us,
        project_conventions=project_conventions,
    )
    return Neurons(engine)
