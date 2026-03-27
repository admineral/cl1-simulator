"use client";

import { FormEvent, useCallback, useEffect, useId, useRef, useState } from "react";
import { Cl1BridgeDeck } from "@/components/cl1/cl1-bridge-deck";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type StimPhase = {
  durationUs: number;
  currentUa: number;
};

type SpikeEvent = {
  id: string;
  tick: number;
  deviceTimestampUs: number;
  neuronId: number;
  amplitude: number;
  timestamp: string;
  source: "synthetic" | "stim";
};

type StimEvent = {
  id: string;
  tick: number;
  deviceTimestampUs: number;
  channel: number;
  leadTimeUs: number;
  burstIndex: number;
  phases: StimPhase[];
  timestamp: string;
};

type PendingStimEvent = {
  id: string;
  dueTimestampUs: number;
  channel: number;
  leadTimeUs: number;
  burstIndex: number;
  phases: StimPhase[];
  createdAtTick: number;
  stimFrequencyHz: number;
  stimAmplitudeUa: number;
};

type Cl1DeviceState = {
  stimTimestampUs: number;
  spikeTimestampUs: number;
  frequencies: number[];
  amplitudes: number[];
  spikeCounts: number[];
  spikeCountsNormalized: number[];
  deadChannels: number[];
  stimmableChannelCount: number;
};

type RecordingState = {
  active: boolean;
  session: string | null;
  frameCount: number;
};

type FeedbackType = "interrupt" | "event" | "reward";

type EnqueuedFeedback = {
  id: string;
  feedbackType: FeedbackType;
  channels: number[];
  frequencyHz: number;
  amplitudeUa: number;
  pulses: number;
  unpredictable: boolean;
  eventName: string;
  enqueuedAtTick: number;
};

type NeuronState = {
  id: number;
  membranePotential: number;
  excitability: number;
  refractoryTicks: number;
  lastSpikeTick: number | null;
  lastStimTick: number | null;
  x: number;
  y: number;
};

type ActivityPoint = {
  tick: number;
  spikeCount: number;
  stimCount: number;
  meanAmplitude: number;
};

type DataStreamEntry = {
  id: string;
  timestampUs: number;
  data: string;
};

type DataStreamState = {
  name: string;
  attributes: Record<string, string>;
  latestTimestampUs: number | null;
  entries: DataStreamEntry[];
};

type SimulatorResponse = {
  running: boolean;
  tick: number;
  tickIntervalMs: number;
  neuronCount: number;
  channelCount: number;
  deviceTimestampUs: number;
  lastUpdated: string;
  spikes: SpikeEvent[];
  stimEvents: StimEvent[];
  pendingStimEvents: PendingStimEvent[];
  neurons: NeuronState[];
  activityHistory: ActivityPoint[];
  dataStreams: DataStreamState[];
  cl1: Cl1DeviceState;
  recording: RecordingState;
  feedbackPending: number;
  lastFeedback: EnqueuedFeedback | null;
  metrics: {
    totalSpikes: number;
    syntheticSpikes: number;
    stimSpikes: number;
    stimEvents: number;
    activeNeurons: number;
    averagePotential: number;
    latestSpikeBurst: number;
    pendingStimEvents: number;
    dataStreams: number;
    stimmableChannels: number;
    recordingFrames: number;
    feedbackPending: number;
  };
};

const initialCl1: Cl1DeviceState = {
  stimTimestampUs: 0,
  spikeTimestampUs: 0,
  frequencies: Array<number>(64).fill(0),
  amplitudes: Array<number>(64).fill(0),
  spikeCounts: Array<number>(64).fill(0),
  spikeCountsNormalized: Array<number>(64).fill(0),
  deadChannels: [0, 4, 7, 56, 63],
  stimmableChannelCount: 59
};

const initialSnapshot: SimulatorResponse = {
  running: false,
  tick: 0,
  tickIntervalMs: 250,
  neuronCount: 16,
  channelCount: 64,
  deviceTimestampUs: 0,
  lastUpdated: new Date(0).toISOString(),
  spikes: [],
  stimEvents: [],
  pendingStimEvents: [],
  neurons: [],
  activityHistory: [],
  dataStreams: [],
  cl1: initialCl1,
  recording: { active: false, session: null, frameCount: 0 },
  feedbackPending: 0,
  lastFeedback: null,
  metrics: {
    totalSpikes: 0,
    syntheticSpikes: 0,
    stimSpikes: 0,
    stimEvents: 0,
    activeNeurons: 0,
    averagePotential: 0,
    latestSpikeBurst: 0,
    pendingStimEvents: 0,
    dataStreams: 0,
    stimmableChannels: 59,
    recordingFrames: 0,
    feedbackPending: 0
  }
};

type ControlAction = "start" | "stop" | "reset" | "tick";

/** Shared canvas width and horizontal insets so population activity and spike raster time axes align. */
const CHART_WIDTH = 880;
const CHART_INSET_X = { left: 36, right: 12 } as const;

async function fetchJson<T>(input: RequestInfo, init?: RequestInit) {
  const response = await fetch(input, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  const json = (await response.json().catch(() => ({}))) as T & { error?: string };

  if (!response.ok) {
    throw new Error(json.error ?? `Request failed with ${response.status}`);
  }

  return json as T;
}

const parseChannels = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item));

/** Stable across SSR + browser — avoids hydration mismatch from `toLocaleTimeString()` differences (Node vs ICU). */
function formatLastUpdatedUtc(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const h = d.getUTCHours().toString().padStart(2, "0");
  const m = d.getUTCMinutes().toString().padStart(2, "0");
  const s = d.getUTCSeconds().toString().padStart(2, "0");
  return `${h}:${m}:${s} UTC`;
}

/** Prefer column counts that divide neuron count evenly so the lattice is a full rectangle (no ragged last row). */
function latticeColumns(count: number): number {
  if (count <= 1) return 1;
  const target = Math.sqrt(count);
  const candidates = new Set<number>();
  for (let d = 1; d * d <= count; d += 1) {
    if (count % d !== 0) continue;
    const a = d;
    const b = count / d;
    if (a > 1 && a < count) candidates.add(a);
    if (b > 1 && b < count) candidates.add(b);
  }
  if (candidates.size === 0) {
    return Math.min(24, Math.max(1, Math.round(target)));
  }
  let best = Math.round(target);
  let bestDist = Infinity;
  for (const c of candidates) {
    if (c > 24) continue;
    const dist = Math.abs(c - target);
    if (dist < bestDist) {
      bestDist = dist;
      best = c;
    }
  }
  return Math.min(24, Math.max(1, best));
}

export default function HomePage() {
  const [snapshot, setSnapshot] = useState<SimulatorResponse>(initialSnapshot);
  const [tickIntervalMs, setTickIntervalMs] = useState(250);
  const [neuronCount, setNeuronCount] = useState(16);
  const [channelsInput, setChannelsInput] = useState("1");
  const [currentUa, setCurrentUa] = useState(1);
  const [leadTimeUs, setLeadTimeUs] = useState(80);
  const [burstCount, setBurstCount] = useState(1);
  const [burstHz, setBurstHz] = useState(20);
  const [streamName, setStreamName] = useState("reward");
  const [streamPayload, setStreamPayload] = useState('{"value": 1}');
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [recordingSessionInput, setRecordingSessionInput] = useState("local-mock");
  const [controlLog, setControlLog] = useState<{ id: string; timeUtc: string; message: string }[]>([]);
  const hydratedControls = useRef(false);

  const pushControlLog = useCallback((message: string) => {
    const timeUtc = formatLastUpdatedUtc(new Date().toISOString());
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    setControlLog((prev) => [{ id, timeUtc, message }, ...prev].slice(0, 48));
  }, []);

  const applySnapshot = useCallback((nextSnapshot: SimulatorResponse, syncControls = false) => {
    setSnapshot(nextSnapshot);

    if (syncControls || !hydratedControls.current) {
      setTickIntervalMs(nextSnapshot.tickIntervalMs);
      setNeuronCount(nextSnapshot.neuronCount);
      hydratedControls.current = true;
    }
  }, []);

  const refresh = useCallback(
    async (syncControls = false) => {
      try {
        const nextSnapshot = await fetchJson<SimulatorResponse>("/api/simulator");
        applySnapshot(nextSnapshot, syncControls);
        setError(null);
      } catch (refreshError) {
        setError(
          refreshError instanceof Error ? refreshError.message : "Could not load simulator state."
        );
      }
    },
    [applySnapshot]
  );

  useEffect(() => {
    void refresh(true);

    const interval = setInterval(() => {
      void refresh(false);
    }, 300);

    return () => clearInterval(interval);
  }, [refresh]);

  const sendControl = async (action: ControlAction, syncControls = true) => {
    setPendingAction(action);

    try {
      const nextSnapshot = await fetchJson<SimulatorResponse>("/api/simulator/control", {
        method: "POST",
        body: JSON.stringify({
          action,
          tickIntervalMs,
          neuronCount
        })
      });

      applySnapshot(nextSnapshot, syncControls);
      setError(null);
      if (action === "start") {
        pushControlLog(`control: start · Δt ${tickIntervalMs} ms · N=${neuronCount}`);
      } else if (action === "stop") {
        pushControlLog("control: stop");
      } else if (action === "reset") {
        pushControlLog("control: reset");
      } else if (action === "tick") {
        pushControlLog(`control: step → tick ${nextSnapshot.tick}`);
      }
    } catch (controlError) {
      setError(
        controlError instanceof Error ? controlError.message : "Simulator control request failed."
      );
    } finally {
      setPendingAction(null);
    }
  };

  const fireStimulus = async (override?: Partial<{ currentUa: number; burstCount: number; burstHz: number }>) => {
    setPendingAction("stim");

    try {
      const nextSnapshot = await fetchJson<SimulatorResponse>("/api/simulator/stim", {
        method: "POST",
        body: JSON.stringify({
          channels: parseChannels(channelsInput),
          currentUa: override?.currentUa ?? currentUa,
          leadTimeUs,
          burstDesign:
            (override?.burstCount ?? burstCount) > 1
              ? {
                  burstCount: override?.burstCount ?? burstCount,
                  burstHz: override?.burstHz ?? burstHz
                }
              : undefined
        })
      });

      applySnapshot(nextSnapshot, false);
      setError(null);
      pushControlLog(`stim: queued · ch [${parseChannels(channelsInput).join(", ")}]`);
    } catch (stimError) {
      setError(stimError instanceof Error ? stimError.message : "Stim request failed.");
    } finally {
      setPendingAction(null);
    }
  };

  const appendDataStream = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPendingAction("stream");

    try {
      const nextSnapshot = await fetchJson<SimulatorResponse>("/api/simulator/data-stream", {
        method: "POST",
        body: JSON.stringify({
          name: streamName,
          data: streamPayload,
          attributes: {
            source: "dashboard"
          }
        })
      });

      applySnapshot(nextSnapshot, false);
      setError(null);
      pushControlLog(`event: stream · ${streamName.trim()}`);
    } catch (streamError) {
      setError(streamError instanceof Error ? streamError.message : "Data stream append failed.");
    } finally {
      setPendingAction(null);
    }
  };

  const startRecordingApi = async () => {
    setPendingAction("recording");
    try {
      const nextSnapshot = await fetchJson<SimulatorResponse>("/api/simulator/recording", {
        method: "POST",
        body: JSON.stringify({
          action: "start",
          session: recordingSessionInput.trim()
        })
      });
      applySnapshot(nextSnapshot, false);
      setError(null);
      pushControlLog(`recording_started · ${nextSnapshot.recording.session ?? "?"}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recording start failed.");
    } finally {
      setPendingAction(null);
    }
  };

  const stopRecordingApi = async (persist: boolean) => {
    setPendingAction("recording");
    try {
      const raw = await fetch("/api/simulator/recording", {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "stop", persist })
      });
      const data = (await raw.json()) as SimulatorResponse & {
        error?: string;
        recordingExport?: { savedPath?: string; frameCount: number };
      };
      if (!raw.ok) {
        throw new Error(data.error ?? `Request failed with ${raw.status}`);
      }
      const { recordingExport: _exp, ...rest } = data;
      applySnapshot(rest as SimulatorResponse, false);
      setError(null);
      const n = _exp?.frameCount ?? 0;
      pushControlLog(
        persist && _exp?.savedPath
          ? `recording_stopped · exported ${n} frames → ${_exp.savedPath}`
          : `recording_stopped · ${n} frames dropped (RAM cleared)`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recording stop failed.");
    } finally {
      setPendingAction(null);
    }
  };

  const sendFeedback = async (payload: {
    feedbackType: FeedbackType;
    channels: number[];
    frequencyHz: number;
    amplitudeUa: number;
    pulses: number;
    unpredictable: boolean;
    eventName: string;
  }) => {
    setPendingAction("feedback");
    try {
      const nextSnapshot = await fetchJson<SimulatorResponse>("/api/simulator/feedback", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      applySnapshot(nextSnapshot, false);
      setError(null);
      pushControlLog(`feedback: enqueued ${payload.feedbackType} · ch [${payload.channels.join(", ")}]`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Feedback failed.");
    } finally {
      setPendingAction(null);
    }
  };

  const busy = pendingAction !== null;
  const neuronCountN = Math.max(snapshot.neurons.length, 1);
  const neuronColumns = latticeColumns(neuronCountN);
  const neuronRows =
    snapshot.neurons.length === 0 ? 1 : Math.ceil(snapshot.neurons.length / neuronColumns);
  const latestSpikes = snapshot.spikes.slice(0, 140);
  const latestStimEvents = snapshot.stimEvents.slice(0, 6);
  const latestDataStreams = snapshot.dataStreams.slice(0, 6);

  return (
    <main className="cortex-app">
      <header className="cortex-hero">
        <div>
          <p className="cortex-kicker">Cortical labs · in vitro neural compute</p>
          <h1 className="cortex-title">CL1 interface loop</h1>
          <p className="cortex-lede">
            Timeline-first simulator dashboard with CL-compatible runtime semantics up top and the bridge/settings stack underneath.
          </p>
        </div>
        <div className="cortex-hero__status">
          <Badge variant={snapshot.running ? "success" : "outline"}>
            {snapshot.running ? "Loop live" : "Idle"}
          </Badge>
          <Badge variant="outline">t = {snapshot.tick}</Badge>
          <Badge variant="outline">{snapshot.deviceTimestampUs} μs</Badge>
          <Badge variant="outline">
            {snapshot.channelCount} ch · {snapshot.metrics.stimmableChannels} stim
          </Badge>
        </div>
      </header>

      <div className="cortex-stage">
        <section className="cortex-runtime-strip" aria-label="Runtime surface">
          <div className="cortex-runtime-strip__card">
            <span className="cortex-runtime-strip__label">Frontend</span>
            <strong>Charts and neuron lattice lead the page</strong>
            <p>Population activity, spike raster, and tissue state are now the first viewport after the hero.</p>
          </div>
          <div className="cortex-runtime-strip__card">
            <span className="cortex-runtime-strip__label">Official-Compatible</span>
            <strong>`cl.open() → Neurons → loop()`</strong>
            <p>The Python package follows the Cortical Labs API mental model and keeps one authoritative device timeline.</p>
          </div>
          <div className="cortex-runtime-strip__card">
            <span className="cortex-runtime-strip__label">Project Conventions</span>
            <strong>64-ch bridge, dead-mask, UDP helpers</strong>
            <p>The dashboard still uses the repo’s local CL1 transport mock and labels those deployment rules separately.</p>
          </div>
        </section>

        <div className="cortex-visual-band">
          <section className="cortex-panel cortex-visual-band__lattice cortex-panel--lattice-rail">
            <div className="cortex-panel__head">
              <div>
                <h2>Neuron lattice</h2>
                <p>Membrane level · bright = near threshold.</p>
              </div>
              <div className="cortex-metrics cortex-metrics--rail">
                <div className="cortex-metric">
                  <span>Active</span>
                  <span>{snapshot.metrics.activeNeurons}</span>
                </div>
                <div className="cortex-metric">
                  <span>⟨V⟩</span>
                  <span>{snapshot.metrics.averagePotential.toFixed(2)}</span>
                </div>
                <div className="cortex-metric">
                  <span>Burst</span>
                  <span>{snapshot.metrics.latestSpikeBurst}</span>
                </div>
              </div>
            </div>
            <div className="cortex-panel__body">
              <div className="cortex-lattice">
                <div
                  className="cortex-neuron-grid cortex-neuron-grid--fill"
                  style={{
                    gridTemplateColumns: `repeat(${neuronColumns}, minmax(0, 1fr))`,
                    gridTemplateRows: `repeat(${neuronRows}, minmax(0, 1fr))`
                  }}
                >
                  {snapshot.neurons.map((neuron) => (
                    <div
                      key={neuron.id}
                      className={`cortex-neuron-cell${neuron.lastStimTick === snapshot.tick ? " cortex-neuron-cell--stim" : ""}`}
                      style={{
                        background: getPotentialColor(neuron.membranePotential, neuron.lastSpikeTick === snapshot.tick),
                        boxShadow:
                          neuron.lastSpikeTick === snapshot.tick
                            ? "0 0 12px rgba(127, 234, 255, 0.4), inset 0 0 10px rgba(255,255,255,0.1)"
                            : "inset 0 0 12px rgba(0,0,0,0.4)"
                      }}
                    >
                      <div>
                        <div className="cortex-neuron-cell__id">n{neuron.id}</div>
                        <div className="cortex-neuron-cell__v">{neuron.membranePotential.toFixed(2)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <div className="cortex-visual-band__cell-spacer" aria-hidden />

          <section className="cortex-panel cortex-readouts__activity">
            <div className="cortex-panel__head">
              <div>
                <h2>Population activity</h2>
                <p>Spikes/tick (solid) · mean amplitude (dashed).</p>
              </div>
            </div>
            <div className="cortex-panel__body">
              <div className="cortex-chart-frame">
                <ActivityChart history={snapshot.activityHistory.slice(-64)} />
              </div>
            </div>
          </section>

          <section className="cortex-panel cortex-readouts__raster">
            <div className="cortex-panel__head">
              <div>
                <h2>Spike raster</h2>
                <p>Time × neuron · amber = stim-linked.</p>
              </div>
              <div className="cortex-chip-row">
                <Badge variant="outline" style={{ fontSize: "0.62rem" }}>
                  Stored {snapshot.metrics.totalSpikes}
                </Badge>
                <Badge variant="outline" style={{ fontSize: "0.62rem" }}>
                  Last sync {formatLastUpdatedUtc(snapshot.lastUpdated)}
                </Badge>
              </div>
            </div>
            <div className="cortex-panel__body">
              <div className="cortex-chart-frame">
                <SpikeRaster spikes={latestSpikes} currentTick={snapshot.tick} neuronCount={snapshot.neuronCount} />
              </div>
            </div>
          </section>
        </div>

        {latestDataStreams.length > 0 ? (
          <section className="cortex-stream-compact" aria-label="Annotation streams">
            {latestDataStreams.map((stream) => (
              <details key={stream.name}>
                <summary>
                  {stream.name} · {stream.latestTimestampUs ?? 0} μs
                </summary>
                {stream.entries.slice(0, 2).map((entry) => (
                  <code key={entry.id}>{entry.data}</code>
                ))}
              </details>
            ))}
          </section>
        ) : null}
      </div>

      <section className="cortex-deck cortex-deck--console" aria-label="Experiment settings">
        <div className="cortex-console">
          <div className="ctl-block ctl-block--transport">
            <header className="ctl-block__head">
              <span className="ctl-block__tag">Run</span>
              <span className="ctl-block__title">Settings · transport &amp; clock</span>
            </header>
            <div className="ctl-block__body">
              <div className="ctl-btn-row" role="toolbar" aria-label="Simulation transport">
                <Button size="sm" disabled={busy} onClick={() => void sendControl("start")}>
                  {pendingAction === "start" ? "…" : "Start"}
                </Button>
                <Button
                  size="sm"
                  disabled={busy || !snapshot.running}
                  variant="secondary"
                  onClick={() => void sendControl("stop", false)}
                >
                  Stop
                </Button>
                <Button size="sm" disabled={busy} variant="outline" onClick={() => void sendControl("tick", false)}>
                  Step
                </Button>
                <Button size="sm" disabled={busy} variant="destructive" onClick={() => void sendControl("reset")}>
                  Reset
                </Button>
                <Button size="sm" disabled={busy} variant="outline" onClick={() => void refresh(false)}>
                  Sync
                </Button>
              </div>
              <div className="ctl-kv-grid">
                <label className="ctl-kv">
                  <span className="ctl-kv__label">Δt (ms)</span>
                  <Input
                    id="tick-ms"
                    className="ctl-input ctl-input--sm"
                    type="number"
                    min={25}
                    step={25}
                    value={tickIntervalMs}
                    onChange={(event) => setTickIntervalMs(Number(event.target.value))}
                  />
                </label>
                <label className="ctl-kv">
                  <span className="ctl-kv__label">Neurons</span>
                  <Input
                    id="n-count"
                    className="ctl-input ctl-input--xs"
                    type="number"
                    min={1}
                    max={256}
                    value={neuronCount}
                    onChange={(event) => setNeuronCount(Number(event.target.value))}
                  />
                </label>
                <div className="ctl-kv ctl-kv--action">
                  <span className="ctl-kv__label" aria-hidden="true">
                    &nbsp;
                  </span>
                  <Button size="sm" disabled={busy} onClick={() => void sendControl("start")}>
                    Apply
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <div className="ctl-block ctl-block--stim">
            <header className="ctl-block__head">
              <span className="ctl-block__tag">MEA</span>
              <span className="ctl-block__title">Settings · stimulation</span>
            </header>
            <div className="ctl-block__body">
              <div className="ctl-kv-grid ctl-kv-grid--stim">
                <label className="ctl-kv ctl-kv--grow">
                  <span className="ctl-kv__label">Channels</span>
                  <Input
                    id="ch"
                    className="ctl-input ctl-input--channels-tight"
                    value={channelsInput}
                    onChange={(event) => setChannelsInput(event.target.value)}
                    placeholder="1,2"
                    title="Comma-separated channel indices"
                  />
                </label>
                <label className="ctl-kv">
                  <span className="ctl-kv__label">I (µA)</span>
                  <Input
                    id="ua"
                    className="ctl-input ctl-input--sm"
                    type="number"
                    min={0}
                    max={3}
                    step={0.1}
                    value={currentUa}
                    onChange={(event) => setCurrentUa(Number(event.target.value))}
                  />
                </label>
                <label className="ctl-kv">
                  <span className="ctl-kv__label">Lead (µs)</span>
                  <Input
                    id="lead"
                    className="ctl-input ctl-input--sm"
                    type="number"
                    min={80}
                    step={40}
                    value={leadTimeUs}
                    onChange={(event) => setLeadTimeUs(Number(event.target.value))}
                  />
                </label>
                <label className="ctl-kv">
                  <span className="ctl-kv__label">Bursts</span>
                  <Input
                    id="nb"
                    className="ctl-input ctl-input--xs"
                    type="number"
                    min={1}
                    step={1}
                    value={burstCount}
                    onChange={(event) => setBurstCount(Number(event.target.value))}
                  />
                </label>
                <label className="ctl-kv">
                  <span className="ctl-kv__label">f (Hz)</span>
                  <Input
                    id="hz"
                    className="ctl-input ctl-input--sm"
                    type="number"
                    min={1}
                    max={200}
                    step={1}
                    value={burstHz}
                    onChange={(event) => setBurstHz(Number(event.target.value))}
                  />
                </label>
              </div>
              <div className="ctl-btn-row">
                <Button size="sm" disabled={busy} onClick={() => void fireStimulus()}>
                  {pendingAction === "stim" ? "…" : "Queue"}
                </Button>
                <Button size="sm" disabled={busy} variant="secondary" onClick={() => void fireStimulus({ currentUa: 0.5 })}>
                  Light
                </Button>
                <Button
                  size="sm"
                  disabled={busy}
                  variant="secondary"
                  onClick={() => void fireStimulus({ currentUa: 1.5, burstCount: 3, burstHz: 40 })}
                >
                  Burst
                </Button>
              </div>
            </div>
          </div>

          <form className="ctl-block ctl-block--stream" onSubmit={appendDataStream}>
            <header className="ctl-block__head">
              <span className="ctl-block__tag">IO</span>
              <span className="ctl-block__title">Settings · data stream</span>
            </header>
            <div className="ctl-block__body ctl-block__body--stream">
              <label className="ctl-kv">
                <span className="ctl-kv__label">Name</span>
                <Input
                  id="s-name"
                  className="ctl-input ctl-input--md"
                  value={streamName}
                  onChange={(event) => setStreamName(event.target.value)}
                />
              </label>
              <label className="ctl-kv ctl-kv--payload">
                <span className="ctl-kv__label">Payload</span>
                <Textarea
                  id="s-payload"
                  className="ctl-textarea ctl-textarea--payload"
                  value={streamPayload}
                  onChange={(event) => setStreamPayload(event.target.value)}
                  rows={1}
                  spellCheck={false}
                />
              </label>
              <div className="ctl-kv ctl-kv--action">
                <span className="ctl-kv__label"> </span>
                <Button size="sm" type="submit" disabled={busy}>
                  {pendingAction === "stream" ? "…" : "Append"}
                </Button>
              </div>
            </div>
          </form>

          <div className="ctl-block ctl-block--queue">
            <header className="ctl-block__head">
              <span className="ctl-block__tag">QUE</span>
              <span className="ctl-block__title">Settings · electrode queue</span>
            </header>
            <div className="ctl-block__body ctl-block__body--queue">
              <div className="ctl-queue-col">
                <span className="ctl-queue-col__label">Pending</span>
                <div className="ui-list">
                  {snapshot.pendingStimEvents.length === 0 ? (
                    <div className="ui-list__row">
                      <span>Queue clear</span>
                      <span>—</span>
                    </div>
                  ) : (
                    snapshot.pendingStimEvents.slice(0, 5).map((event) => (
                      <div key={event.id} className="ui-list__row">
                        <strong style={{ fontFamily: "var(--font-mono)" }}>ch {event.channel}</strong>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem" }}>{event.dueTimestampUs} µs</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
              <div className="ctl-queue-col">
                <span className="ctl-queue-col__label">Delivered</span>
                <div className="ui-list">
                  {latestStimEvents.length === 0 ? (
                    <div className="ui-list__row">
                      <span>No deliveries</span>
                      <span>—</span>
                    </div>
                  ) : (
                    latestStimEvents.map((event) => (
                      <div key={event.id} className="ui-list__row">
                        <strong style={{ fontFamily: "var(--font-mono)" }}>ch {event.channel}</strong>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem" }}>{event.deviceTimestampUs} µs</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className={`cortex-statusline${error ? " cortex-statusline--error" : ""}`}>
          {error
            ? error
            : `Telemetry · synthetic ${snapshot.metrics.syntheticSpikes} · evoked ${snapshot.metrics.stimSpikes} · pending stim ${snapshot.metrics.pendingStimEvents} · ${busy ? pendingAction : "ready"}`}
        </div>
      </section>

      <section className="cortex-deck cortex-deck--cl1" aria-label="CL1 operations mock">
        <Cl1BridgeDeck
          running={snapshot.running}
          tick={snapshot.tick}
          deviceTimestampUs={snapshot.deviceTimestampUs}
          pendingStim={snapshot.metrics.pendingStimEvents}
          feedbackPending={snapshot.feedbackPending}
          totalSpikes={snapshot.metrics.totalSpikes}
          stimDeliveries={snapshot.stimEvents.length}
          dataStreamNames={snapshot.dataStreams.length}
          cl1={snapshot.cl1}
          recordingSession={
            snapshot.recording.active ? (snapshot.recording.session ?? "") : recordingSessionInput
          }
          recordingActive={snapshot.recording.active}
          recordingFrameCount={snapshot.recording.frameCount}
          busy={busy}
          onRecordingSessionChange={setRecordingSessionInput}
          onRecordingStart={() => void startRecordingApi()}
          onRecordingStop={() => void stopRecordingApi(false)}
          onRecordingStopExport={() => void stopRecordingApi(true)}
          onFeedbackSend={sendFeedback}
          controlLog={controlLog}
        />
      </section>
    </main>
  );
}

function ActivityChart({ history }: { history: ActivityPoint[] }) {
  const uid = useId().replace(/:/g, "");
  const gradId = `act-bg-${uid}`;

  if (history.length === 0) {
    return (
      <div className="ui-note ui-note--chart-empty">Start the loop — activity traces populate as the tissue clock advances.</div>
    );
  }

  const width = CHART_WIDTH;
  const height = 120;
  const m = {
    l: CHART_INSET_X.left,
    r: CHART_INSET_X.right,
    t: 14,
    b: 14
  };
  const plotW = width - m.l - m.r;
  const plotH = height - m.t - m.b;
  const maxSpikes = Math.max(...history.map((point) => point.spikeCount), 1);
  const maxAmplitude = Math.max(...history.map((point) => point.meanAmplitude), 0.1);

  const xAt = (index: number, n: number) =>
    n <= 1 ? m.l + plotW / 2 : m.l + (index / (n - 1)) * plotW;
  const nPts = history.length;

  const spikeLine = history
    .map((point, index) => {
      const x = xAt(index, nPts);
      const y = m.t + plotH - (point.spikeCount / maxSpikes) * plotH;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const amplitudeLine = history
    .map((point, index) => {
      const x = xAt(index, nPts);
      const y = m.t + plotH - (point.meanAmplitude / maxAmplitude) * plotH;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="100%"
      className="cortex-chart-svg ui-chart ui-chart--paired"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(46,228,208,0.14)" />
          <stop offset="100%" stopColor="rgba(46,228,208,0.02)" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width={width} height={height} rx="12" fill={`url(#${gradId})`} stroke="rgba(120,175,210,0.12)" />
      {Array.from({ length: 5 }, (_, index) => {
        const y = m.t + (index / 4) * plotH;
        return (
          <line key={y} x1={m.l} y1={y} x2={m.l + plotW} y2={y} stroke="rgba(120,175,210,0.1)" strokeWidth="1" />
        );
      })}
      <path d={spikeLine} fill="none" stroke="#2ee4d0" strokeWidth="2.5" strokeLinecap="round" />
      <path
        d={amplitudeLine}
        fill="none"
        stroke="#ffb14a"
        strokeWidth="2"
        strokeDasharray="8 6"
        strokeLinecap="round"
        opacity={0.95}
      />
    </svg>
  );
}

function SpikeRaster({
  spikes,
  currentTick,
  neuronCount
}: {
  spikes: SpikeEvent[];
  currentTick: number;
  neuronCount: number;
}) {
  const rasterUid = useId().replace(/:/g, "");
  const clipId = `raster-clip-${rasterUid}`;
  const nRows = Math.max(1, neuronCount);

  if (spikes.length === 0) {
    return (
      <div className="ui-note ui-note--chart-empty">
        Raster fills once the culture fires — run ticks or queue stimulation to seed events.
      </div>
    );
  }

  const width = CHART_WIDTH;
  const height = 172;
  const m = { l: CHART_INSET_X.left, r: CHART_INSET_X.right, t: 24, b: 30 };
  const plotW = width - m.l - m.r;
  const plotH = height - m.t - m.b;
  const rowH = plotH / nRows;
  const tickHalf = Math.max(1.5, Math.min(5, rowH * 0.42));

  const spikeTicks = spikes.map((s) => s.tick);
  const minTick = Math.min(currentTick, ...spikeTicks);
  const maxTick = Math.max(currentTick, ...spikeTicks);
  const tickRange = Math.max(maxTick - minTick, 1);

  const xAt = (t: number) => m.l + ((t - minTick) / tickRange) * plotW;
  const yAt = (neuronId: number) => {
    const row = Math.min(Math.max(0, neuronId), nRows - 1);
    return m.t + plotH - (row + 0.5) * rowH;
  };

  const nowX = xAt(currentTick);
  const xGridSteps = 6;
  const showRowLines = nRows <= 48;
  const rowStride = nRows > 32 ? Math.ceil(nRows / 16) : 1;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="100%"
      className="raster-svg ui-chart ui-chart--raster"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={`Spike raster, ${spikes.length} events across ${nRows} neurons`}
    >
      <defs>
        <clipPath id={clipId}>
          <rect x={m.l} y={m.t} width={plotW} height={plotH} rx="2" />
        </clipPath>
      </defs>

      <rect width={width} height={height} rx="11" fill="#05080c" stroke="rgba(120,175,210,0.14)" strokeWidth="1" />

      <text className="raster-title" x={m.l} y={17}>
        Spike raster · tick axis
      </text>

      <rect
        x={m.l}
        y={m.t}
        width={plotW}
        height={plotH}
        fill="rgba(6, 10, 14, 0.98)"
        stroke="rgba(46, 228, 208, 0.14)"
        strokeWidth="1"
      />

      {showRowLines
        ? Array.from({ length: nRows + 1 }, (_, i) => {
            const y = m.t + plotH - i * rowH;
            return (
              <line
                key={`h-${i}`}
                x1={m.l}
                y1={y}
                x2={m.l + plotW}
                y2={y}
                stroke="rgba(255,255,255,0.045)"
                strokeWidth={i === 0 || i === nRows ? 1 : 0.5}
              />
            );
          })
        : null}

      {!showRowLines
        ? Array.from({ length: nRows + 1 }, (_, i) =>
            i % rowStride === 0 || i === nRows ? (
              <line
                key={`h-s-${i}`}
                x1={m.l}
                y1={m.t + plotH - i * rowH}
                x2={m.l + plotW}
                y2={m.t + plotH - i * rowH}
                stroke="rgba(255,255,255,0.04)"
                strokeWidth="0.5"
              />
            ) : null
          )
        : null}

      {Array.from({ length: xGridSteps + 1 }, (_, i) => {
        const x = m.l + (i / xGridSteps) * plotW;
        return (
          <line
            key={`v-${i}`}
            x1={x}
            y1={m.t}
            x2={x}
            y2={m.t + plotH}
            stroke="rgba(46,228,208,0.055)"
            strokeWidth="1"
          />
        );
      })}

      <line
        x1={nowX}
        x2={nowX}
        y1={m.t}
        y2={m.t + plotH}
        stroke="rgba(46, 228, 208, 0.55)"
        strokeWidth="1.25"
        strokeDasharray="5 4"
        pointerEvents="none"
      />

      <g clipPath={`url(#${clipId})`}>
        {spikes.map((spike) => {
          const x = xAt(spike.tick);
          const y = yAt(spike.neuronId);
          const stim = spike.source === "stim";
          const alpha = 0.62 + spike.amplitude * 0.38;
          return (
            <line
              key={spike.id}
              x1={x}
              x2={x}
              y1={y - tickHalf}
              y2={y + tickHalf}
              stroke={stim ? "#ff9f2e" : "#62e6ff"}
              strokeWidth={stim ? 2.35 : 1.85}
              strokeLinecap="round"
              opacity={alpha}
            />
          );
        })}
      </g>

      <text className="raster-axis" x={m.l - 6} y={m.t + plotH - 0.5 * rowH} textAnchor="end" dominantBaseline="middle">
        0
      </text>
      <text className="raster-axis" x={m.l - 6} y={m.t + 0.5 * rowH} textAnchor="end" dominantBaseline="middle">
        {nRows - 1}
      </text>
      <text
        className="raster-axis"
        x={m.l - 6}
        y={m.t + plotH * 0.5}
        textAnchor="end"
        dominantBaseline="middle"
        fill="rgba(107,132,153,0.6)"
        fontSize="7.5px"
      >
        n
      </text>

      <text className="raster-axis" x={m.l} y={height - 10} textAnchor="start">
        t = {minTick}
      </text>
      <text className="raster-axis" x={m.l + plotW * 0.5} y={height - 10} textAnchor="middle">
        now → {currentTick}
      </text>
      <text className="raster-axis" x={m.l + plotW} y={height - 10} textAnchor="end">
        t = {maxTick}
      </text>

      <g transform={`translate(${m.l + plotW - 4}, ${m.t + 11})`} textAnchor="end">
        <line x1={-56} y1={0} x2={-42} y2={0} stroke="#62e6ff" strokeWidth={2} strokeLinecap="round" />
        <text className="raster-axis" x={-38} y={3.5} textAnchor="start">
          synthetic
        </text>
        <line x1={-56} y1={14} x2={-42} y2={14} stroke="#ff9f2e" strokeWidth={2} strokeLinecap="round" />
        <text className="raster-axis" x={-38} y={17.5} textAnchor="start">
          evoked
        </text>
      </g>
    </svg>
  );
}

function getPotentialColor(potential: number, firing: boolean) {
  if (firing) {
    return "radial-gradient(circle at 45% 35%, rgba(255,255,255,0.95), rgba(127,234,255,0.95) 38%, rgba(44,156,255,0.85) 100%)";
  }

  if (potential > 0.78) {
    return "radial-gradient(circle at 45% 35%, rgba(186,245,234,0.95), rgba(46,228,208,0.55) 52%, rgba(8,64,58,0.95) 100%)";
  }

  if (potential > 0.45) {
    return "radial-gradient(circle at 45% 35%, rgba(91,140,160,0.9), rgba(32,58,72,0.95) 55%, rgba(10,16,22,1) 100%)";
  }

  return "radial-gradient(circle at 45% 35%, rgba(70,88,102,0.85), rgba(28,38,48,0.96) 56%, rgba(8,10,13,1) 100%)";
}
