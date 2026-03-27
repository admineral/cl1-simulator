export type SpikeEvent = {
  id: string;
  tick: number;
  deviceTimestampUs: number;
  neuronId: number;
  amplitude: number;
  timestamp: string;
  source: "synthetic" | "stim";
};

export type StimEvent = {
  id: string;
  tick: number;
  deviceTimestampUs: number;
  channel: number;
  leadTimeUs: number;
  burstIndex: number;
  phases: StimPhase[];
  timestamp: string;
};

export type NeuronState = {
  id: number;
  membranePotential: number;
  excitability: number;
  refractoryTicks: number;
  lastSpikeTick: number | null;
  lastStimTick: number | null;
  x: number;
  y: number;
};

export type ActivityPoint = {
  tick: number;
  spikeCount: number;
  stimCount: number;
  meanAmplitude: number;
};

export type StimPhase = {
  durationUs: number;
  currentUa: number;
};

export type StimDesignInput = {
  phases: StimPhase[];
};

export type BurstDesignInput = {
  burstCount: number;
  burstHz: number;
};

export type PendingStimEvent = {
  id: string;
  dueTimestampUs: number;
  channel: number;
  leadTimeUs: number;
  burstIndex: number;
  phases: StimPhase[];
  createdAtTick: number;
  /** Packed into mock STIM frame (Hz) for this electrode. */
  stimFrequencyHz: number;
  /** Packed into mock STIM frame (µA) — summary of phase currents. */
  stimAmplitudeUa: number;
};

/** Last device-style 64-channel frame from the in-process mock (for tests / UDP parity). */
export type Cl1DeviceState = {
  stimTimestampUs: number;
  spikeTimestampUs: number;
  frequencies: number[];
  amplitudes: number[];
  spikeCounts: number[];
  /** clamp(count, 35) / 35 on active channels only; dead always 0. */
  spikeCountsNormalized: number[];
  deadChannels: number[];
  stimmableChannelCount: number;
};

export type DataStreamEntry = {
  id: string;
  timestampUs: number;
  data: string;
};

export type DataStreamState = {
  name: string;
  attributes: Record<string, string>;
  latestTimestampUs: number | null;
  entries: DataStreamEntry[];
};

export type RecordingFrame = {
  tick: number;
  deviceTimestampUs: number;
  spikeCounts: number[];
  frequencies: number[];
  amplitudes: number[];
};

export type RecordingState = {
  active: boolean;
  session: string | null;
  frameCount: number;
};

export type FeedbackType = "interrupt" | "event" | "reward";

export type FeedbackRequest = {
  feedbackType: FeedbackType;
  channels: number[];
  frequencyHz?: number;
  amplitudeUa?: number;
  pulses?: number;
  unpredictable?: boolean;
  eventName?: string;
};

export type EnqueuedFeedback = {
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

export type SimulatorSnapshot = {
  running: boolean;
  tick: number;
  tickIntervalMs: number;
  neuronCount: number;
  channelCount: number;
  deviceTimestampUs: number;
  lastUpdated: string;
  spikes: SpikeEvent[];
  stimEvents: StimEvent[];
  neurons: NeuronState[];
  activityHistory: ActivityPoint[];
  pendingStimEvents: PendingStimEvent[];
  dataStreams: DataStreamState[];
  cl1: Cl1DeviceState;
  recording: RecordingState;
  feedbackPending: number;
  lastFeedback: EnqueuedFeedback | null;
};

export type StartOptions = {
  tickIntervalMs?: number;
  neuronCount?: number;
};

export type StimRequest = {
  channel?: number;
  channels?: number[];
  currentUa?: number;
  stimDesign?: StimDesignInput;
  burstDesign?: BurstDesignInput;
  leadTimeUs?: number;
};

export type DataStreamRequest = {
  name: string;
  data: string;
  timestampUs?: number;
  attributes?: Record<string, string>;
};
