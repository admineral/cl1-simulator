from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from cl_sim.api.neurons import Neurons
from cl_sim.training.ablation import noise_ablation, shuffled_ablation, zero_ablation
from cl_sim.training.types import Readout, ReadoutConfig, TrainingObservation


@dataclass(frozen=True, slots=True)
class TrainingStepResult:
    sample_id: str
    prediction: object
    spike_rounds: tuple[tuple[float, ...], ...]
    ablation: str | None


class CL1TrainingSession:
    def __init__(
        self,
        neurons: Neurons,
        *,
        readout: Readout,
        config: ReadoutConfig | None = None,
    ) -> None:
        self.neurons = neurons
        self.readout = readout
        self.config = config or ReadoutConfig()
        self._stream = self.neurons.create_data_stream(
            "training.lifecycle",
            attributes={"convention": "project-specific-cl1-training"},
        )

    def run_sample(
        self,
        *,
        sample_id: str,
        rounds: int = 1,
        ablation: Literal["noise", "zero", "shuffled"] | None = None,
    ) -> TrainingStepResult:
        spike_rounds: list[tuple[float, ...]] = []
        for round_index in range(rounds):
            tick = next(self.neurons.loop(max_ticks=1))
            counts = [0.0] * (tick.frames.channel_count or 0)
            for spike in tick.analysis.spikes:
                counts[spike.channel] += 1.0
            spike_rounds.append(tuple(counts))
            self._stream.append(
                f"sample={sample_id};round={round_index};spikes={len(tick.analysis.spikes)}"
            )

        round_tuple = tuple(spike_rounds)
        if ablation == "noise":
            round_tuple = noise_ablation(round_tuple)
        elif ablation == "zero":
            round_tuple = zero_ablation(round_tuple)
        elif ablation == "shuffled":
            round_tuple = shuffled_ablation(round_tuple)

        observation = TrainingObservation(sample_id=sample_id, spike_rounds=round_tuple)
        prediction = self.readout.predict(observation)
        return TrainingStepResult(
            sample_id=sample_id,
            prediction=prediction,
            spike_rounds=round_tuple,
            ablation=ablation,
        )
