import { describe, expect, it } from "vitest";
import {
  CL1_SPIKE_PACKET_SIZE,
  CL1_STIM_PACKET_SIZE,
  packSpikePacket,
  packStimPacket,
  unpackSpikePacket,
  unpackStimPacket
} from "@/lib/simulator/packets";

describe("CL1 packet mock (UDP parity)", () => {
  it("round-trips STIM (520 bytes)", () => {
    const ts = 1_704_000_000_000_000;
    const freqs = Array.from({ length: 64 }, (_, i) => (i === 5 ? 20 : 0));
    const amps = Array.from({ length: 64 }, (_, i) => (i === 5 ? 1.5 : 0));
    const buf = packStimPacket(ts, freqs, amps);
    expect(buf.byteLength).toBe(CL1_STIM_PACKET_SIZE);
    const out = unpackStimPacket(buf);
    expect(out.timestampUs).toBe(ts);
    expect(out.frequencies[5]).toBeCloseTo(20);
    expect(out.amplitudes[5]).toBeCloseTo(1.5);
    expect(out.amplitudes[0]).toBe(0);
  });

  it("round-trips SPIKE (264 bytes)", () => {
    const ts = 99_000;
    const counts = Array.from({ length: 64 }, (_, i) => i * 0.1);
    const buf = packSpikePacket(ts, counts);
    expect(buf.byteLength).toBe(CL1_SPIKE_PACKET_SIZE);
    const out = unpackSpikePacket(buf);
    expect(out.timestampUs).toBe(ts);
    expect(out.spikeCounts[3]).toBeCloseTo(0.3);
  });
});
