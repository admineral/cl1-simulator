/** CL1 invariants shared by the mock device (see docs/CL1-udp-protocol.md). */

export const CL1_TOTAL_CHANNELS = 64;

/** Hardware-dead electrodes — never stimulate or learn on these indices. */
export const CL1_DEAD_CHANNELS: ReadonlySet<number> = new Set([0, 4, 7, 56, 63]);

export const CL1_STIMMABLE_CHANNELS: ReadonlySet<number> = (() => {
  const s = new Set<number>();
  for (let ch = 1; ch < 63; ch += 1) {
    if (!CL1_DEAD_CHANNELS.has(ch)) s.add(ch);
  }
  return s;
})();

export const CL1_ACTIVE_CHANNEL_COUNT = CL1_STIMMABLE_CHANNELS.size;

/** Sorted stimmable indices for mapping model neurons → electrodes. */
export const CL1_ACTIVE_CHANNEL_LIST: readonly number[] = Array.from(CL1_STIMMABLE_CHANNELS).sort(
  (a, b) => a - b
);

/** Doc bounds (re-validate against official docs before hardware). */
export const CL1_MAX_AMPLITUDE_UA = 3.0;
export const CL1_PULSE_WIDTH_STEP_US = 20;
export const CL1_MAX_PULSE_WIDTH_US = 10_000;
export const CL1_MAX_CHARGE_NC = 3.0;

/** Model-side spike normalization (CL1 model patterns). */
export const CL1_SPIKE_CLAMP = 35.0;

export function assertStimmableChannel(channel: number): void {
  if (!Number.isInteger(channel) || channel < 0 || channel >= CL1_TOTAL_CHANNELS) {
    throw new Error(`Channel ${channel} is out of range. Expected 0–${CL1_TOTAL_CHANNELS - 1}.`);
  }
  if (!CL1_STIMMABLE_CHANNELS.has(channel)) {
    throw new Error(
      `Channel ${channel} is not stimmable (dead or reserved). Stimmable indices omit ${[
        ...CL1_DEAD_CHANNELS
      ]
        .sort((a, b) => a - b)
        .join(", ")}.`
    );
  }
}

export function zeroDeadChannels<T extends number>(values: T[]): T[] {
  const next = [...values] as T[];
  CL1_DEAD_CHANNELS.forEach((ch) => {
    next[ch] = 0 as T;
  });
  return next;
}

export function normalizeSpikeCountsForModel(counts: number[]): number[] {
  return counts.map((c, i) => {
    if (CL1_DEAD_CHANNELS.has(i)) return 0;
    const v = Math.min(Math.max(c, 0), CL1_SPIKE_CLAMP);
    return v / CL1_SPIKE_CLAMP;
  });
}
