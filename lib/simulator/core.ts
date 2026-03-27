import {
  CL1_ACTIVE_CHANNEL_COUNT,
  CL1_ACTIVE_CHANNEL_LIST,
  CL1_DEAD_CHANNELS,
  CL1_TOTAL_CHANNELS,
  assertStimmableChannel,
  normalizeSpikeCountsForModel
} from "@/lib/simulator/cl1-constants";
import {
  ActivityPoint,
  Cl1DeviceState,
  DataStreamRequest,
  DataStreamState,
  EnqueuedFeedback,
  FeedbackRequest,
  NeuronState,
  PendingStimEvent,
  RecordingFrame,
  SimulatorSnapshot,
  SpikeEvent,
  StartOptions,
  StimEvent,
  StimPhase,
  StimRequest
} from "@/lib/simulator/types";

const MAX_SPIKES = 300;
const MAX_STIM_EVENTS = 80;
const MAX_ACTIVITY_HISTORY = 72;
const MAX_DATA_STREAM_ENTRIES = 40;
const DEFAULT_INTERVAL_MS = 250;
const DEFAULT_NEURON_COUNT = 16;
const MAX_RECORDING_FRAMES = 6000;

const emptyCl1Device = (deviceTimestampUs: number): Cl1DeviceState => ({
  stimTimestampUs: deviceTimestampUs,
  spikeTimestampUs: deviceTimestampUs,
  frequencies: Array<number>(CL1_TOTAL_CHANNELS).fill(0),
  amplitudes: Array<number>(CL1_TOTAL_CHANNELS).fill(0),
  spikeCounts: Array<number>(CL1_TOTAL_CHANNELS).fill(0),
  spikeCountsNormalized: Array<number>(CL1_TOTAL_CHANNELS).fill(0),
  deadChannels: [...CL1_DEAD_CHANNELS].sort((a, b) => a - b),
  stimmableChannelCount: CL1_ACTIVE_CHANNEL_COUNT
});

const createId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const buildNeuronLayout = (count: number): NeuronState[] => {
  const columns = Math.ceil(Math.sqrt(count));
  const rows = Math.ceil(count / columns);

  return Array.from({ length: count }, (_, id) => ({
    id,
    membranePotential: Number((0.22 + (id % 5) * 0.07).toFixed(3)),
    excitability: Number((0.82 + (id % 7) * 0.035).toFixed(3)),
    refractoryTicks: 0,
    lastSpikeTick: null,
    lastStimTick: null,
    x: columns === 1 ? 0.5 : (id % columns) / (columns - 1),
    y: rows === 1 ? 0.5 : Math.floor(id / columns) / (rows - 1)
  }));
};

const defaultStimPhases = (currentUa: number): StimPhase[] => [
  { durationUs: 160, currentUa: -Math.abs(currentUa) },
  { durationUs: 160, currentUa: Math.abs(currentUa) }
];

const requireFinite = (value: number, label: string) => {
  if (!Number.isFinite(value)) {
    throw new Error(`${label} must be a finite number.`);
  }
};

const validateStimPhases = (phases: StimPhase[]) => {
  if (phases.length === 0 || phases.length % 2 !== 0) {
    throw new Error("StimDesign must contain 2, 4, or 6 phase arguments represented as 1-3 phase pairs.");
  }

  if (phases.length > 3) {
    throw new Error("StimDesign supports up to 3 phases.");
  }

  for (let index = 0; index < phases.length; index += 1) {
    const phase = phases[index];
    requireFinite(phase.durationUs, `Phase ${index + 1} durationUs`);
    requireFinite(phase.currentUa, `Phase ${index + 1} currentUa`);

    if (phase.durationUs <= 0 || phase.durationUs % 20 !== 0) {
      throw new Error(`Phase ${index + 1} duration must be positive and divisible by 20us.`);
    }

    if (Math.abs(phase.currentUa) > 3.0) {
      throw new Error(`Phase ${index + 1} current must be within +/-3.0uA.`);
    }

    const chargePc = Math.abs(phase.currentUa) * phase.durationUs;

    if (chargePc > 3000) {
      throw new Error(`Phase ${index + 1} exceeds the 3.0nC charge limit.`);
    }

    if (index > 0) {
      const previous = phases[index - 1];

      if (Math.sign(previous.currentUa) === Math.sign(phase.currentUa)) {
        throw new Error("Adjacent stimulation phases must alternate polarity.");
      }
    }
  }
};

const normalizeStimRequest = (request: StimRequest) => {
  const channels = request.channels ?? (typeof request.channel === "number" ? [request.channel] : [1]);
  const uniqueChannels = [...new Set(channels)];

  if (uniqueChannels.length === 0) {
    throw new Error("Stim request must target at least one channel.");
  }

  uniqueChannels.forEach((ch) => assertStimmableChannel(ch));

  const phases =
    request.stimDesign?.phases ?? defaultStimPhases(clamp(request.currentUa ?? 1.0, 0, 3.0));

  validateStimPhases(phases);

  const leadTimeUs = request.leadTimeUs ?? 80;

  if (leadTimeUs < 80 || leadTimeUs % 40 !== 0) {
    throw new Error("leadTimeUs must be at least 80 and divisible by 40.");
  }

  const burstCount = request.burstDesign?.burstCount ?? 1;
  const burstHz = request.burstDesign?.burstHz ?? 0;

  if (!Number.isInteger(burstCount) || burstCount <= 0) {
    throw new Error("burstCount must be a positive integer.");
  }

  if (burstCount > 1) {
    if (!Number.isFinite(burstHz) || burstHz <= 0 || burstHz > 200) {
      throw new Error("burstHz must be > 0 and <= 200.");
    }
  }

  return {
    channels: uniqueChannels,
    phases,
    leadTimeUs,
    burstCount,
    burstHz
  };
};

const normalizeFeedbackRequest = (request: FeedbackRequest): Omit<EnqueuedFeedback, "id" | "enqueuedAtTick"> => {
  const { feedbackType } = request;
  if (feedbackType !== "interrupt" && feedbackType !== "event" && feedbackType !== "reward") {
    throw new Error("feedbackType must be interrupt, event, or reward.");
  }
  const channels = [...new Set(request.channels)];
  if (channels.length === 0) {
    throw new Error("Feedback requires at least one channel.");
  }
  channels.forEach((ch) => assertStimmableChannel(ch));
  const frequencyHz = clamp(request.frequencyHz ?? 20, 1, 200);
  const amplitudeUa = clamp(request.amplitudeUa ?? 0.5, 0, 3);
  const pulses = Math.max(1, Math.min(1000, Math.floor(request.pulses ?? 1)));
  return {
    feedbackType,
    channels,
    frequencyHz,
    amplitudeUa,
    pulses,
    unpredictable: Boolean(request.unpredictable),
    eventName: (request.eventName ?? "").slice(0, 64)
  };
};

class SimulatorCore {
  private running = false;
  private tick = 0;
  private tickIntervalMs = DEFAULT_INTERVAL_MS;
  private neuronCount = DEFAULT_NEURON_COUNT;
  private channelCount = CL1_TOTAL_CHANNELS;
  private deviceTimestampUs = 0;
  private neurons = buildNeuronLayout(DEFAULT_NEURON_COUNT);
  private spikes: SpikeEvent[] = [];
  private stimEvents: StimEvent[] = [];
  private pendingStimEvents: PendingStimEvent[] = [];
  private dataStreams = new Map<string, DataStreamState>();
  private activityHistory: ActivityPoint[] = [];
  private timer: NodeJS.Timeout | null = null;
  private lastUpdated = new Date().toISOString();
  private cl1Device: Cl1DeviceState = emptyCl1Device(0);
  private recordingActive = false;
  private recordingSession: string | null = null;
  private recordingFrames: RecordingFrame[] = [];
  private feedbackQueue: EnqueuedFeedback[] = [];
  private lastFeedback: EnqueuedFeedback | null = null;

  getSnapshot(): SimulatorSnapshot {
    return {
      running: this.running,
      tick: this.tick,
      tickIntervalMs: this.tickIntervalMs,
      neuronCount: this.neuronCount,
      channelCount: this.channelCount,
      deviceTimestampUs: this.deviceTimestampUs,
      lastUpdated: this.lastUpdated,
      spikes: [...this.spikes],
      stimEvents: [...this.stimEvents],
      neurons: this.neurons.map((neuron) => ({ ...neuron })),
      activityHistory: [...this.activityHistory],
      pendingStimEvents: [...this.pendingStimEvents],
      dataStreams: [...this.dataStreams.values()].map((stream) => ({
        ...stream,
        attributes: { ...stream.attributes },
        entries: [...stream.entries]
      })),
      cl1: {
        ...this.cl1Device,
        frequencies: [...this.cl1Device.frequencies],
        amplitudes: [...this.cl1Device.amplitudes],
        spikeCounts: [...this.cl1Device.spikeCounts],
        spikeCountsNormalized: [...this.cl1Device.spikeCountsNormalized],
        deadChannels: [...this.cl1Device.deadChannels]
      },
      recording: {
        active: this.recordingActive,
        session: this.recordingSession,
        frameCount: this.recordingFrames.length
      },
      feedbackPending: this.feedbackQueue.length,
      lastFeedback: this.lastFeedback ? { ...this.lastFeedback, channels: [...this.lastFeedback.channels] } : null
    };
  }

  start(options: StartOptions = {}) {
    let shouldReschedule = false;

    if (typeof options.tickIntervalMs === "number") {
      const nextTickIntervalMs = Math.max(25, options.tickIntervalMs);
      shouldReschedule = shouldReschedule || nextTickIntervalMs !== this.tickIntervalMs;
      this.tickIntervalMs = nextTickIntervalMs;
    }

    if (typeof options.neuronCount === "number") {
      const nextNeuronCount = Math.max(1, Math.min(256, options.neuronCount));

      if (nextNeuronCount !== this.neuronCount) {
        this.neuronCount = nextNeuronCount;
        this.neurons = buildNeuronLayout(this.neuronCount);
        this.spikes = [];
        this.activityHistory = [];
      }
    }

    if (this.running) {
      if (shouldReschedule && this.timer) {
        clearTimeout(this.timer);
        this.timer = null;
        this.scheduleNextTick();
      }

      return this.getSnapshot();
    }

    this.running = true;
    this.lastUpdated = new Date().toISOString();
    this.scheduleNextTick();
    return this.getSnapshot();
  }

  stop() {
    this.running = false;

    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }

    this.lastUpdated = new Date().toISOString();
    return this.getSnapshot();
  }

  reset() {
    this.stop();
    this.tick = 0;
    this.deviceTimestampUs = 0;
    this.neurons = buildNeuronLayout(this.neuronCount);
    this.spikes = [];
    this.stimEvents = [];
    this.pendingStimEvents = [];
    this.activityHistory = [];
    this.dataStreams.clear();
    this.cl1Device = emptyCl1Device(0);
    this.recordingActive = false;
    this.recordingSession = null;
    this.recordingFrames = [];
    this.feedbackQueue = [];
    this.lastFeedback = null;
    this.lastUpdated = new Date().toISOString();
    return this.getSnapshot();
  }

  timestamp() {
    return this.deviceTimestampUs;
  }

  tickOnce() {
    this.tick += 1;
    this.deviceTimestampUs += this.tickIntervalMs * 1000;

    const stimFreq = new Array<number>(CL1_TOTAL_CHANNELS).fill(0);
    const stimAmp = new Array<number>(CL1_TOTAL_CHANNELS).fill(0);
    const channelSpikes = new Array<number>(CL1_TOTAL_CHANNELS).fill(0);

    this.applyFeedbackToStimArrays(stimFreq, stimAmp);

    const deliveredStims = this.flushPendingStimEvents(stimFreq, stimAmp, channelSpikes);
    const syntheticSpikes = this.generateSyntheticSpikes(channelSpikes);
    this.recordActivity([...deliveredStims.evokedSpikes, ...syntheticSpikes], deliveredStims.events.length);

    CL1_DEAD_CHANNELS.forEach((ch) => {
      stimFreq[ch] = 0;
      stimAmp[ch] = 0;
      channelSpikes[ch] = 0;
    });

    this.cl1Device = {
      stimTimestampUs: this.deviceTimestampUs,
      spikeTimestampUs: this.deviceTimestampUs,
      frequencies: [...stimFreq],
      amplitudes: [...stimAmp],
      spikeCounts: [...channelSpikes],
      spikeCountsNormalized: normalizeSpikeCountsForModel(channelSpikes),
      deadChannels: [...CL1_DEAD_CHANNELS].sort((a, b) => a - b),
      stimmableChannelCount: CL1_ACTIVE_CHANNEL_COUNT
    };

    if (this.recordingActive) {
      this.recordingFrames.push({
        tick: this.tick,
        deviceTimestampUs: this.deviceTimestampUs,
        spikeCounts: [...channelSpikes],
        frequencies: [...stimFreq],
        amplitudes: [...stimAmp]
      });
      if (this.recordingFrames.length > MAX_RECORDING_FRAMES) {
        this.recordingFrames = this.recordingFrames.slice(-MAX_RECORDING_FRAMES);
      }
    }

    this.lastUpdated = new Date().toISOString();
    return this.getSnapshot();
  }

  startRecording(session: string) {
    const name = session.trim();
    if (!name) {
      throw new Error("Recording session name is required.");
    }
    this.recordingActive = true;
    this.recordingSession = name;
    this.recordingFrames = [];
    this.lastUpdated = new Date().toISOString();
    return this.getSnapshot();
  }

  stopRecording(): { session: string | null; frames: RecordingFrame[] } {
    const session = this.recordingSession;
    const frames = [...this.recordingFrames];
    this.recordingActive = false;
    this.recordingSession = null;
    this.recordingFrames = [];
    this.lastUpdated = new Date().toISOString();
    return { session, frames };
  }

  enqueueFeedback(request: FeedbackRequest) {
    const partial = normalizeFeedbackRequest(request);
    const item: EnqueuedFeedback = {
      ...partial,
      id: createId(),
      enqueuedAtTick: this.tick
    };
    this.feedbackQueue.push(item);
    this.lastUpdated = new Date().toISOString();
    return this.getSnapshot();
  }

  private applyFeedbackToStimArrays(stimFreq: number[], stimAmp: number[]) {
    if (this.feedbackQueue.length === 0) {
      return;
    }
    for (const fb of this.feedbackQueue) {
      if (fb.feedbackType === "interrupt") {
        this.pendingStimEvents = [];
      }
      for (const ch of fb.channels) {
        stimFreq[ch] = Math.max(stimFreq[ch], fb.frequencyHz);
        stimAmp[ch] = Math.max(stimAmp[ch], fb.amplitudeUa);
      }
    }
    this.lastFeedback = this.feedbackQueue[this.feedbackQueue.length - 1] ?? null;
    this.feedbackQueue = [];
  }

  triggerStim(request: StimRequest = {}) {
    const normalized = normalizeStimRequest(request);
    const scheduled: PendingStimEvent[] = [];
    const burstSpacingUs =
      normalized.burstCount > 1 ? Math.round(1_000_000 / normalized.burstHz) : 0;

    const stimFrequencyHz = normalized.burstCount > 1 ? normalized.burstHz : 20;
    const stimAmplitudeUa = normalized.phases.reduce(
      (max, phase) => Math.max(max, Math.abs(phase.currentUa)),
      0
    );

    for (const channel of normalized.channels) {
      for (let burstIndex = 0; burstIndex < normalized.burstCount; burstIndex += 1) {
        scheduled.push({
          id: createId(),
          dueTimestampUs:
            this.deviceTimestampUs + normalized.leadTimeUs + burstIndex * burstSpacingUs,
          channel,
          leadTimeUs: normalized.leadTimeUs,
          burstIndex,
          phases: normalized.phases,
          createdAtTick: this.tick,
          stimFrequencyHz,
          stimAmplitudeUa
        });
      }
    }

    this.pendingStimEvents = [...this.pendingStimEvents, ...scheduled].sort(
      (left, right) => left.dueTimestampUs - right.dueTimestampUs
    );
    this.lastUpdated = new Date().toISOString();
    return this.getSnapshot();
  }

  appendDataStream(request: DataStreamRequest) {
    if (!request.name.trim()) {
      throw new Error("Data stream name is required.");
    }

    const streamName = request.name.trim();
    const stream =
      this.dataStreams.get(streamName) ??
      ({
        name: streamName,
        attributes: {},
        latestTimestampUs: null,
        entries: []
      } satisfies DataStreamState);

    const timestampUs = request.timestampUs ?? this.deviceTimestampUs;

    if (stream.latestTimestampUs !== null && timestampUs <= stream.latestTimestampUs) {
      throw new Error("Data stream timestamps must be strictly increasing.");
    }

    stream.attributes = {
      ...stream.attributes,
      ...(request.attributes ?? {})
    };

    stream.latestTimestampUs = timestampUs;
    stream.entries = [
      {
        id: createId(),
        timestampUs,
        data: request.data
      },
      ...stream.entries
    ].slice(0, MAX_DATA_STREAM_ENTRIES);

    this.dataStreams.set(streamName, stream);
    this.lastUpdated = new Date().toISOString();
    return this.getSnapshot();
  }

  private scheduleNextTick() {
    if (!this.running) {
      return;
    }

    this.timer = setTimeout(() => {
      this.tickOnce();
      this.scheduleNextTick();
    }, this.tickIntervalMs);
  }

  private flushPendingStimEvents(
    stimFreq: number[],
    stimAmp: number[],
    channelSpikes: number[]
  ) {
    const ready = this.pendingStimEvents.filter((event) => event.dueTimestampUs <= this.deviceTimestampUs);
    this.pendingStimEvents = this.pendingStimEvents.filter(
      (event) => event.dueTimestampUs > this.deviceTimestampUs
    );

    for (const scheduled of ready) {
      stimFreq[scheduled.channel] = Math.max(stimFreq[scheduled.channel], scheduled.stimFrequencyHz);
      stimAmp[scheduled.channel] = Math.max(stimAmp[scheduled.channel], scheduled.stimAmplitudeUa);
    }

    const stimEvents: StimEvent[] = [];
    const evokedSpikes: SpikeEvent[] = [];

    for (const scheduled of ready) {
      stimEvents.push({
        id: scheduled.id,
        tick: this.tick,
        deviceTimestampUs: scheduled.dueTimestampUs,
        channel: scheduled.channel,
        leadTimeUs: scheduled.leadTimeUs,
        burstIndex: scheduled.burstIndex,
        phases: scheduled.phases,
        timestamp: new Date().toISOString()
      });

      const neuronId = (scheduled.channel + this.tick) % this.neuronCount;
      const neuron = this.neurons[neuronId];
      const totalCurrent = scheduled.phases.reduce(
        (total, phase) => total + Math.abs(phase.currentUa),
        0
      );
      const amplitude = clamp(totalCurrent / 6, 0.2, 1);

      neuron.membranePotential = clamp(neuron.membranePotential + amplitude * 0.45, 0, 1);
      neuron.refractoryTicks = 1;
      neuron.lastStimTick = this.tick;
      neuron.lastSpikeTick = this.tick;

      const spikeAmp = Number((0.55 + amplitude * 0.4).toFixed(3));
      channelSpikes[scheduled.channel] += spikeAmp;

      evokedSpikes.push({
        id: createId(),
        tick: this.tick,
        deviceTimestampUs: scheduled.dueTimestampUs,
        neuronId,
        amplitude: spikeAmp,
        timestamp: new Date().toISOString(),
        source: "stim"
      });
    }

    this.stimEvents = [...stimEvents, ...this.stimEvents].slice(0, MAX_STIM_EVENTS);
    this.spikes = [...evokedSpikes, ...this.spikes].slice(0, MAX_SPIKES);

    return { events: stimEvents, evokedSpikes };
  }

  private generateSyntheticSpikes(channelSpikes: number[]): SpikeEvent[] {
    const spikeBurstSize = Math.max(1, Math.round(this.neuronCount * 0.25));
    const spikesForTick: SpikeEvent[] = [];

    for (const neuron of this.neurons) {
      if (neuron.refractoryTicks > 0) {
        neuron.refractoryTicks -= 1;
      }

      const baseDrive = 0.05 + ((this.tick + neuron.id * 3) % 9) * 0.016;
      const noise = Math.random() * 0.08;
      neuron.membranePotential = clamp(
        neuron.membranePotential * 0.82 + baseDrive * neuron.excitability + noise,
        0,
        1
      );

      const threshold = 0.78 - (neuron.excitability - 0.8) * 0.22;
      const shouldFire = neuron.refractoryTicks === 0 && neuron.membranePotential >= threshold;

      if (!shouldFire) {
        continue;
      }

      neuron.refractoryTicks = 2;
      neuron.lastSpikeTick = this.tick;
      neuron.membranePotential = clamp(0.18 + Math.random() * 0.16, 0, 1);

      const amp = Number((0.2 + Math.random() * 0.8).toFixed(3));
      spikesForTick.push({
        id: createId(),
        tick: this.tick,
        deviceTimestampUs: this.deviceTimestampUs,
        neuronId: neuron.id,
        amplitude: amp,
        timestamp: new Date().toISOString(),
        source: "synthetic"
      });

      const electrode = CL1_ACTIVE_CHANNEL_LIST[neuron.id % CL1_ACTIVE_CHANNEL_LIST.length];
      channelSpikes[electrode] += amp;

      if (spikesForTick.length >= spikeBurstSize) {
        break;
      }
    }

    this.spikes = [...spikesForTick, ...this.spikes].slice(0, MAX_SPIKES);
    return spikesForTick;
  }

  private recordActivity(spikesForTick: SpikeEvent[], stimCount: number) {
    const meanAmplitude =
      spikesForTick.length === 0
        ? 0
        : spikesForTick.reduce((total, spike) => total + spike.amplitude, 0) / spikesForTick.length;

    const point: ActivityPoint = {
      tick: this.tick,
      spikeCount: spikesForTick.length,
      stimCount,
      meanAmplitude: Number(meanAmplitude.toFixed(3))
    };

    const existingIndex = this.activityHistory.findIndex((entry) => entry.tick === this.tick);

    if (existingIndex >= 0) {
      const existing = this.activityHistory[existingIndex];
      const combinedSpikeCount = existing.spikeCount + point.spikeCount;
      const combinedMeanAmplitude =
        combinedSpikeCount === 0
          ? 0
          : (existing.meanAmplitude * existing.spikeCount + point.meanAmplitude * point.spikeCount) /
            combinedSpikeCount;

      this.activityHistory[existingIndex] = {
        tick: this.tick,
        spikeCount: combinedSpikeCount,
        stimCount: existing.stimCount + point.stimCount,
        meanAmplitude: Number(combinedMeanAmplitude.toFixed(3))
      };
    } else {
      this.activityHistory = [...this.activityHistory, point].slice(-MAX_ACTIVITY_HISTORY);
    }
  }
}

declare global {
  var __cl1Simulator__: SimulatorCore | undefined;
}

export const simulator =
  globalThis.__cl1Simulator__ ?? (globalThis.__cl1Simulator__ = new SimulatorCore());
