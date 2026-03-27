from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import cl
from cl_sim.api.stim import BurstDesign, ChannelSet, StimDesign
from cl_sim.api.types import LoopTick, Spike as ClSpike, StimEvent as ClStimEvent
from cl_sim.transport.protocol import (
    SPIKE_PACKET_SIZE,
    STIM_PACKET_SIZE,
    pack_spike_packet,
    pack_stim_packet,
)


MAX_SPIKES = 300
MAX_STIM_EVENTS = 80
MAX_ACTIVITY_HISTORY = 72
MAX_DATA_STREAM_ENTRIES = 40
DEFAULT_INTERVAL_MS = 250
DEFAULT_NEURON_COUNT = 16
TOTAL_CHANNELS = 64


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_id() -> str:
    return f"{int(time.time() * 1_000_000):x}-{os.urandom(3).hex()}"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def build_neuron_layout(count: int) -> list[dict[str, Any]]:
    columns = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / columns))
    neurons = []
    for neuron_id in range(count):
        neurons.append(
            {
                "id": neuron_id,
                "membranePotential": round(0.22 + (neuron_id % 5) * 0.07, 3),
                "excitability": round(0.82 + (neuron_id % 7) * 0.035, 3),
                "refractoryTicks": 0,
                "lastSpikeTick": None,
                "lastStimTick": None,
                "x": 0.5 if columns == 1 else (neuron_id % columns) / (columns - 1),
                "y": 0.5 if rows == 1 else math.floor(neuron_id / columns) / (rows - 1),
            }
        )
    return neurons


@dataclass
class RecordingHandle:
    session: str
    temp_path: Path
    active: bool
    frame_count: int = 0


class PythonDashboardSimulator:
    """Dashboard bridge on top of the official-style local CL simulator runtime.

    The `cl.open()` / `Neurons` runtime below follows the official Cortical Labs mental model.
    The JSON shape returned here is project-specific dashboard/bridge state used by the Next.js UI.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tick_interval_ms = DEFAULT_INTERVAL_MS
        self._neuron_count = DEFAULT_NEURON_COUNT
        self._project_conventions = cl.ProjectConventionProfile.repo_default()
        self._neurons = self._open_runtime()
        self._running = False
        self._worker: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._tick = 0
        self._last_updated = utc_now_iso()
        self._last_tick: LoopTick | None = None
        self._spikes: list[dict[str, Any]] = []
        self._stim_events: list[dict[str, Any]] = []
        self._pending_stim_events: list[dict[str, Any]] = []
        self._data_streams: dict[str, dict[str, Any]] = {}
        self._activity_history: list[dict[str, Any]] = []
        self._feedback_queue: list[dict[str, Any]] = []
        self._last_feedback: dict[str, Any] | None = None
        self._recording: RecordingHandle | None = None
        self._recording_stream = None
        self._neurons_view = build_neuron_layout(self._neuron_count)
        self._last_cl1 = self._empty_cl1_state()

    def shutdown(self) -> None:
        with self._lock:
            self._running = False
            self._stop_event.set()
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        with self._lock:
            if self._recording_stream is not None:
                self._recording_stream.close()
                self._recording_stream = None
            self._neurons.close()

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._summarized_snapshot()

    def get_device_payload(self) -> dict[str, Any]:
        with self._lock:
            stim_buf = pack_stim_packet(
                int(self._last_cl1["stimTimestampUs"]),
                self._last_cl1["frequencies"],
                self._last_cl1["amplitudes"],
            )
            spike_buf = pack_spike_packet(
                int(self._last_cl1["spikeTimestampUs"]),
                self._last_cl1["spikeCounts"],
            )
            return {
                "cl1": self._last_cl1,
                "stimPacketBase64": base64.b64encode(stim_buf).decode("ascii"),
                "spikePacketBase64": base64.b64encode(spike_buf).decode("ascii"),
                "stimPacketSize": STIM_PACKET_SIZE,
                "spikePacketSize": SPIKE_PACKET_SIZE,
            }

    def start(self, *, tick_interval_ms: int | None, neuron_count: int | None) -> dict[str, Any]:
        with self._lock:
            if tick_interval_ms is not None:
                self._tick_interval_ms = max(25, int(tick_interval_ms))
            if neuron_count is not None and int(neuron_count) != self._neuron_count:
                self._neuron_count = max(1, min(256, int(neuron_count)))
                self._neurons_view = build_neuron_layout(self._neuron_count)
                self._spikes.clear()
                self._activity_history.clear()

            if self._running:
                self._last_updated = utc_now_iso()
                return self._summarized_snapshot()

            self._running = True
            self._stop_event.clear()
            self._worker = threading.Thread(target=self._run_loop, name="cl-sim-python-loop", daemon=True)
            self._worker.start()
            self._last_updated = utc_now_iso()
            return self._summarized_snapshot()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._running = False
            self._stop_event.set()
            worker = self._worker
            self._worker = None
            self._last_updated = utc_now_iso()
        if worker is not None and worker.is_alive():
            worker.join(timeout=1.5)
        return self.get_snapshot()

    def reset(self) -> dict[str, Any]:
        self.stop()
        with self._lock:
            if self._recording_stream is not None:
                self._recording_stream.close()
                self._recording_stream = None
            self._neurons.close()
            self._neurons = self._open_runtime()
            self._tick = 0
            self._last_tick = None
            self._spikes.clear()
            self._stim_events.clear()
            self._pending_stim_events.clear()
            self._data_streams.clear()
            self._activity_history.clear()
            self._feedback_queue.clear()
            self._last_feedback = None
            self._recording = None
            self._neurons_view = build_neuron_layout(self._neuron_count)
            self._last_cl1 = self._empty_cl1_state()
            self._last_updated = utc_now_iso()
            return self._summarized_snapshot()

    def tick_once(self) -> dict[str, Any]:
        with self._lock:
            self._apply_feedback_locked()
            self._advance_locked()
            return self._summarized_snapshot()

    def queue_stim(self, body: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            channels = body.get("channels")
            channel = body.get("channel")
            if channels is None:
                if channel is None:
                    channels = [1]
                else:
                    channels = [int(channel)]
            channels = [int(value) for value in channels]
            design_payload = body.get("stimDesign")
            current_ua = body.get("currentUa", 1.0)
            if design_payload and isinstance(design_payload, Mapping):
                phases = []
                for phase in design_payload.get("phases", []):
                    phases.extend([int(phase["durationUs"]), float(phase["currentUa"])])
                design = StimDesign(*phases)
            else:
                design = float(current_ua)

            burst_payload = body.get("burstDesign") or {}
            burst = BurstDesign(
                burst_count=int(burst_payload.get("burstCount", 1)),
                burst_hz=int(burst_payload.get("burstHz", 0)),
            )
            lead_time_us = int(body.get("leadTimeUs", 80))
            scheduled = self._neurons.stim(
                ChannelSet(channels),
                design,
                burst,
                lead_time_us=lead_time_us,
            )

            effective_design = design if isinstance(design, StimDesign) else StimDesign.from_scalar_current(float(design))
            stim_frequency_hz = burst.burst_hz if burst.burst_count > 1 else 20
            stim_amplitude_ua = max(abs(phase.current_ua) for phase in effective_design.phases)
            for queued in scheduled:
                for channel_id in queued.operation.channels:
                    self._pending_stim_events.append(
                        {
                            "id": create_id(),
                            "dueTimestampUs": queued.scheduled_timestamp_us,
                            "channel": channel_id,
                            "leadTimeUs": queued.operation.lead_time_us,
                            "burstIndex": queued.burst_index,
                            "phases": [
                                {
                                    "durationUs": phase.duration_us,
                                    "currentUa": phase.current_ua,
                                }
                                for phase in queued.operation.design.phases
                            ],
                            "createdAtTick": self._tick,
                            "stimFrequencyHz": stim_frequency_hz,
                            "stimAmplitudeUa": stim_amplitude_ua,
                        }
                    )
            self._pending_stim_events.sort(key=lambda item: item["dueTimestampUs"])
            self._last_updated = utc_now_iso()
            return self._summarized_snapshot()

    def append_data_stream(self, body: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            name = str(body.get("name", "")).strip()
            if not name:
                raise ValueError("Data stream name is required.")
            payload = str(body.get("data", ""))
            attrs = {
                str(key): str(value)
                for key, value in dict(body.get("attributes", {})).items()
            }
            stream = self._neurons.create_data_stream(name, attributes=attrs)
            record = stream.append(
                payload,
                timestamp_us=body.get("timestampUs"),
            )
            self._ingest_data_stream_record_locked(record)
            self._last_updated = utc_now_iso()
            return self._summarized_snapshot()

    def enqueue_feedback(self, body: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            feedback_type = str(body.get("feedbackType", "")).strip()
            channels = [int(value) for value in body.get("channels", [])]
            if not feedback_type or not channels:
                raise ValueError("feedbackType and channels[] are required.")
            payload = {
                "id": create_id(),
                "feedbackType": feedback_type,
                "channels": channels,
                "frequencyHz": int(body.get("frequencyHz", 20)),
                "amplitudeUa": float(body.get("amplitudeUa", 0.5)),
                "pulses": max(1, int(body.get("pulses", 1))),
                "unpredictable": bool(body.get("unpredictable", False)),
                "eventName": str(body.get("eventName", ""))[:64],
                "enqueuedAtTick": self._tick,
            }
            self._feedback_queue.append(payload)
            self._last_updated = utc_now_iso()
            return self._summarized_snapshot()

    def start_recording(self, session: str) -> dict[str, Any]:
        with self._lock:
            name = session.strip()
            if not name:
                raise ValueError("Recording session name is required.")
            if self._recording_stream is not None:
                self._recording_stream.close()
                self._recording_stream = None

            temp_dir = Path(tempfile.gettempdir()) / "cl-sim-python"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{self._safe_basename(name)}-{int(time.time() * 1000)}.jsonl"
            self._recording_stream = self._neurons.record(str(temp_path), metadata={"session": name})
            self._recording = RecordingHandle(session=name, temp_path=temp_path, active=True, frame_count=0)
            self._last_updated = utc_now_iso()
            return self._summarized_snapshot()

    def stop_recording(self, *, persist: bool) -> dict[str, Any]:
        with self._lock:
            handle = self._recording
            if self._recording_stream is not None:
                self._recording_stream.close()
                self._recording_stream = None
            self._recording = None

        saved_path: str | None = None
        frame_count = 0
        if handle is not None:
            frame_count = handle.frame_count
            if persist:
                target_dir = Path.cwd() / "recordings"
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / f"{self._safe_basename(handle.session)}-{int(time.time() * 1000)}.jsonl"
                shutil.move(str(handle.temp_path), target_path)
                saved_path = str(target_path)
            elif handle.temp_path.exists():
                handle.temp_path.unlink(missing_ok=True)

        snapshot = self.get_snapshot()
        snapshot["recordingExport"] = {"savedPath": saved_path, "frameCount": frame_count}
        return snapshot

    def _open_runtime(self):
        return cl.open(project_conventions=self._project_conventions)

    def _empty_cl1_state(self) -> dict[str, Any]:
        return {
            "stimTimestampUs": 0,
            "spikeTimestampUs": 0,
            "frequencies": [0.0] * TOTAL_CHANNELS,
            "amplitudes": [0.0] * TOTAL_CHANNELS,
            "spikeCounts": [0.0] * TOTAL_CHANNELS,
            "spikeCountsNormalized": [0.0] * TOTAL_CHANNELS,
            "deadChannels": list(self._project_conventions.dead_channels),
            "stimmableChannelCount": len(self._project_conventions.stimmable_channels),
        }

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self._tick_interval_ms / 1000):
            with self._lock:
                if not self._running:
                    return
                self._apply_feedback_locked()
                self._advance_locked()

    def _apply_feedback_locked(self) -> None:
        if not self._feedback_queue:
            return
        for item in list(self._feedback_queue):
            if item["feedbackType"] == "interrupt":
                self._neurons.interrupt()
                self._pending_stim_events.clear()
            if item["amplitudeUa"] > 0:
                self._neurons.stim(
                    ChannelSet(item["channels"]),
                    float(item["amplitudeUa"]),
                    BurstDesign(
                        burst_count=int(item["pulses"]),
                        burst_hz=int(item["frequencyHz"]),
                    ),
                    lead_time_us=80,
                )
                for burst_index in range(int(item["pulses"])):
                    due_ts = self._neurons.timestamp() + 80
                    if item["pulses"] > 1 and item["frequencyHz"] > 0:
                        due_ts += int(round(1_000_000 / item["frequencyHz"])) * burst_index
                    for channel_id in item["channels"]:
                        self._pending_stim_events.append(
                            {
                                "id": create_id(),
                                "dueTimestampUs": due_ts,
                                "channel": channel_id,
                                "leadTimeUs": 80,
                                "burstIndex": burst_index,
                                "phases": [
                                    {"durationUs": 160, "currentUa": -abs(item["amplitudeUa"])},
                                    {"durationUs": 160, "currentUa": abs(item["amplitudeUa"])},
                                ],
                                "createdAtTick": self._tick,
                                "stimFrequencyHz": int(item["frequencyHz"]),
                                "stimAmplitudeUa": float(item["amplitudeUa"]),
                            }
                        )
            self._last_feedback = item
        self._feedback_queue.clear()
        self._pending_stim_events.sort(key=lambda entry: entry["dueTimestampUs"])

    def _advance_locked(self) -> None:
        tick = next(self._neurons.loop(max_ticks=1, interval_us=self._tick_interval_ms * 1000))
        self._tick += 1
        self._last_tick = tick
        self._last_updated = utc_now_iso()

        spike_counts = [0.0] * TOTAL_CHANNELS
        spike_ids_this_tick = set()
        for spike in tick.analysis.spikes:
            spike_counts[spike.channel] += 1.0
            event = self._spike_to_dashboard(spike)
            self._spikes.insert(0, event)
            spike_ids_this_tick.add(event["id"])
        self._spikes = self._spikes[:MAX_SPIKES]

        delivered_stim_ids = set()
        frequencies = [0.0] * TOTAL_CHANNELS
        amplitudes = [0.0] * TOTAL_CHANNELS
        delivered_pairs = {(stim.channel, stim.timestamp_us, stim.burst_index) for stim in tick.analysis.stims}
        self._pending_stim_events = [
            event
            for event in self._pending_stim_events
            if (event["channel"], event["dueTimestampUs"], event["burstIndex"]) not in delivered_pairs
        ]

        for stim in tick.analysis.stims:
            delivered = self._stim_to_dashboard(stim)
            self._stim_events.insert(0, delivered)
            delivered_stim_ids.add(delivered["id"])
            amplitudes[stim.channel] = max(
                amplitudes[stim.channel],
                max(abs(phase.current_ua) for phase in stim.phases),
            )
            frequencies[stim.channel] = max(frequencies[stim.channel], 20.0)
        self._stim_events = self._stim_events[:MAX_STIM_EVENTS]

        for record in tick.analysis.data_streams:
            self._ingest_data_stream_record_locked(record)

        self._last_cl1 = {
            "stimTimestampUs": tick.timestamp_us,
            "spikeTimestampUs": tick.timestamp_us,
            "frequencies": frequencies,
            "amplitudes": amplitudes,
            "spikeCounts": spike_counts,
            "spikeCountsNormalized": self._normalize_spike_counts(spike_counts),
            "deadChannels": list(self._project_conventions.dead_channels),
            "stimmableChannelCount": len(self._project_conventions.stimmable_channels),
        }
        self._update_neurons_view_locked(tick, spike_ids_this_tick, delivered_stim_ids)
        self._record_activity_locked(spike_counts, len(tick.analysis.stims))

        if self._recording is not None and self._recording.active:
            self._recording.frame_count += tick.frames.frame_count

    def _update_neurons_view_locked(
        self,
        tick: LoopTick,
        spike_ids_this_tick: set[str],
        delivered_stim_ids: set[str],
    ) -> None:
        spike_channels = {spike["channel"] for spike in self._spikes[: len(spike_ids_this_tick)]}
        stim_channels = {stim["channel"] for stim in self._stim_events[: len(delivered_stim_ids)]}
        for neuron in self._neurons_view:
            channel = neuron["id"] % TOTAL_CHANNELS
            baseline = 0.22 + (neuron["id"] % 5) * 0.07
            spike_boost = 0.4 if channel in spike_channels else 0.0
            stim_boost = 0.18 if channel in stim_channels else 0.0
            potential = clamp(baseline + spike_boost + stim_boost, 0.0, 1.25)
            neuron["membranePotential"] = round(potential, 3)
            neuron["refractoryTicks"] = 1 if channel in spike_channels else 0
            neuron["lastSpikeTick"] = self._tick if channel in spike_channels else neuron["lastSpikeTick"]
            neuron["lastStimTick"] = self._tick if channel in stim_channels else neuron["lastStimTick"]

    def _record_activity_locked(self, spike_counts: list[float], stim_count: int) -> None:
        total_spikes = int(sum(spike_counts))
        nonzero = [count for count in spike_counts if count > 0]
        mean_amp = round(sum(nonzero) / len(nonzero), 3) if nonzero else 0.0
        self._activity_history.append(
            {
                "tick": self._tick,
                "spikeCount": total_spikes,
                "stimCount": stim_count,
                "meanAmplitude": mean_amp,
            }
        )
        self._activity_history = self._activity_history[-MAX_ACTIVITY_HISTORY:]

    def _normalize_spike_counts(self, counts: list[float]) -> list[float]:
        dead = set(self._project_conventions.dead_channels)
        normalized = []
        for index, count in enumerate(counts):
            if index in dead:
                normalized.append(0.0)
            else:
                normalized.append(min(max(count, 0.0), 35.0) / 35.0)
        return normalized

    def _spike_to_dashboard(self, spike: ClSpike) -> dict[str, Any]:
        return {
            "id": create_id(),
            "tick": self._tick,
            "deviceTimestampUs": spike.timestamp_us,
            "neuronId": spike.channel % max(1, self._neuron_count),
            "channel": spike.channel,
            "amplitude": round(max((abs(value) for value in spike.samples), default=0.0), 4),
            "timestamp": utc_now_iso(),
            "source": spike.source,
        }

    def _stim_to_dashboard(self, stim: ClStimEvent) -> dict[str, Any]:
        return {
            "id": create_id(),
            "tick": self._tick,
            "deviceTimestampUs": stim.timestamp_us,
            "channel": stim.channel,
            "leadTimeUs": stim.lead_time_us,
            "burstIndex": stim.burst_index,
            "phases": [
                {"durationUs": phase.duration_us, "currentUa": phase.current_ua}
                for phase in stim.phases
            ],
            "timestamp": utc_now_iso(),
        }

    def _ingest_data_stream_record_locked(self, record) -> None:
        stream = self._data_streams.get(record.name)
        if stream is None:
            stream = {
                "name": record.name,
                "attributes": dict(record.attributes),
                "latestTimestampUs": None,
                "entries": [],
            }
            self._data_streams[record.name] = stream
        stream["attributes"] = {**stream["attributes"], **dict(record.attributes)}
        stream["latestTimestampUs"] = record.timestamp_us
        stream["entries"].insert(
            0,
            {
                "id": create_id(),
                "timestampUs": record.timestamp_us,
                "data": record.payload,
            },
        )
        stream["entries"] = stream["entries"][:MAX_DATA_STREAM_ENTRIES]

    def _summarized_snapshot(self) -> dict[str, Any]:
        active_neurons = sum(1 for neuron in self._neurons_view if neuron["lastSpikeTick"] == self._tick)
        average_potential = sum(neuron["membranePotential"] for neuron in self._neurons_view) / max(
            len(self._neurons_view),
            1,
        )
        latest_activity = self._activity_history[-1] if self._activity_history else None
        snapshot = {
            "running": self._running,
            "tick": self._tick,
            "tickIntervalMs": self._tick_interval_ms,
            "neuronCount": self._neuron_count,
            "channelCount": TOTAL_CHANNELS,
            "deviceTimestampUs": self._neurons.timestamp(),
            "lastUpdated": self._last_updated,
            "spikes": list(self._spikes),
            "stimEvents": list(self._stim_events),
            "pendingStimEvents": list(self._pending_stim_events),
            "neurons": [dict(neuron) for neuron in self._neurons_view],
            "activityHistory": list(self._activity_history),
            "dataStreams": [dict(stream) for stream in self._data_streams.values()],
            "cl1": dict(self._last_cl1),
            "recording": {
                "active": self._recording is not None and self._recording.active,
                "session": None if self._recording is None else self._recording.session,
                "frameCount": 0 if self._recording is None else self._recording.frame_count,
            },
            "feedbackPending": len(self._feedback_queue),
            "lastFeedback": None if self._last_feedback is None else dict(self._last_feedback),
            "metrics": {
                "totalSpikes": len(self._spikes),
                "syntheticSpikes": sum(1 for spike in self._spikes if spike["source"] == "synthetic"),
                "stimSpikes": sum(1 for spike in self._spikes if spike["source"] == "stim"),
                "stimEvents": len(self._stim_events),
                "activeNeurons": active_neurons,
                "averagePotential": round(average_potential, 3),
                "latestSpikeBurst": 0 if latest_activity is None else latest_activity["spikeCount"],
                "pendingStimEvents": len(self._pending_stim_events),
                "dataStreams": len(self._data_streams),
                "stimmableChannels": len(self._project_conventions.stimmable_channels),
                "recordingFrames": 0 if self._recording is None else self._recording.frame_count,
                "feedbackPending": len(self._feedback_queue),
            },
        }
        return snapshot

    def _safe_basename(self, value: str) -> str:
        sanitized = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
        sanitized = sanitized[:48].strip("_")
        return sanitized or "session"


SIMULATOR = PythonDashboardSimulator()


class SimulatorRequestHandler(BaseHTTPRequestHandler):
    server_version = "CLSimPython/0.1"

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        try:
            if method == "GET" and parsed.path == "/health":
                self._write_json({"ok": True, "backend": "python"}, status=HTTPStatus.OK)
                return

            if method == "GET" and parsed.path == "/simulator":
                self._write_json(SIMULATOR.get_snapshot(), status=HTTPStatus.OK)
                return

            if method == "GET" and parsed.path == "/simulator/device":
                self._write_json(SIMULATOR.get_device_payload(), status=HTTPStatus.OK)
                return

            body = self._read_json_body() if method == "POST" else {}
            if method == "POST" and parsed.path == "/simulator/control":
                action = str(body.get("action", "tick"))
                if action == "start":
                    payload = SIMULATOR.start(
                        tick_interval_ms=body.get("tickIntervalMs"),
                        neuron_count=body.get("neuronCount"),
                    )
                elif action == "stop":
                    payload = SIMULATOR.stop()
                elif action == "reset":
                    payload = SIMULATOR.reset()
                elif action == "tick":
                    payload = SIMULATOR.tick_once()
                else:
                    self._write_json({"error": f"Unsupported action: {action}"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json(payload, status=HTTPStatus.OK)
                return

            if method == "POST" and parsed.path == "/simulator/stim":
                self._write_json(SIMULATOR.queue_stim(body), status=HTTPStatus.OK)
                return

            if method == "POST" and parsed.path == "/simulator/data-stream":
                self._write_json(SIMULATOR.append_data_stream(body), status=HTTPStatus.OK)
                return

            if method == "POST" and parsed.path == "/simulator/feedback":
                self._write_json(SIMULATOR.enqueue_feedback(body), status=HTTPStatus.OK)
                return

            if method == "POST" and parsed.path == "/simulator/recording":
                action = str(body.get("action", ""))
                if action == "start":
                    payload = SIMULATOR.start_recording(str(body.get("session", "")))
                elif action == "stop":
                    payload = SIMULATOR.stop_recording(persist=bool(body.get("persist", False)))
                else:
                    self._write_json({"error": "action must be start or stop."}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json(payload, status=HTTPStatus.OK)
                return

            self._write_json({"error": f"Unsupported path: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as error:
            self._write_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - defensive server surface
            self._write_json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _write_json(self, payload: Mapping[str, Any], *, status: HTTPStatus) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Python backend for the CL simulator dashboard")
    parser.add_argument("--host", default=os.getenv("CL_SIM_PYTHON_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CL_SIM_PYTHON_PORT", "8765")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SimulatorRequestHandler)
    try:
        print(f"CL simulator Python service listening on http://{args.host}:{args.port}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        SIMULATOR.shutdown()


if __name__ == "__main__":
    main()
