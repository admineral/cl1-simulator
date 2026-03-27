import { CL1_ACTIVE_CHANNEL_COUNT } from "@/lib/simulator/cl1-constants";
import { SimulatorSnapshot } from "@/lib/simulator/types";

export const summarizeActivity = (snapshot: SimulatorSnapshot) => {
  const latestSynthetic = snapshot.spikes.filter((event) => event.source === "synthetic").length;
  const latestStim = snapshot.spikes.filter((event) => event.source === "stim").length;
  const activeNeurons = snapshot.neurons.filter((neuron) => neuron.lastSpikeTick === snapshot.tick).length;
  const averagePotential =
    snapshot.neurons.reduce((total, neuron) => total + neuron.membranePotential, 0) /
    Math.max(snapshot.neurons.length, 1);
  const latestActivity = snapshot.activityHistory.at(-1);

  return {
    ...snapshot,
    metrics: {
      totalSpikes: snapshot.spikes.length,
      syntheticSpikes: latestSynthetic,
      stimSpikes: latestStim,
      stimEvents: snapshot.stimEvents.length,
      activeNeurons,
      averagePotential: Number(averagePotential.toFixed(3)),
      latestSpikeBurst: latestActivity?.spikeCount ?? 0,
      pendingStimEvents: snapshot.pendingStimEvents.length,
      dataStreams: snapshot.dataStreams.length,
      stimmableChannels: CL1_ACTIVE_CHANNEL_COUNT,
      recordingFrames: snapshot.recording.frameCount,
      feedbackPending: snapshot.feedbackPending
    }
  };
};
