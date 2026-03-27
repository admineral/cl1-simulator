/**
 * Little-endian STIM / SPIKE layouts matching scripts/cl1_multiport_protocol_helper.py
 * (uint64 ts | float32[64] freqs | float32[64] amps) and (uint64 ts | float32[64] counts).
 */

import { CL1_TOTAL_CHANNELS } from "@/lib/simulator/cl1-constants";

export const CL1_STIM_PACKET_SIZE = 8 + CL1_TOTAL_CHANNELS * 4 + CL1_TOTAL_CHANNELS * 4;
export const CL1_SPIKE_PACKET_SIZE = 8 + CL1_TOTAL_CHANNELS * 4;

function writeU64(view: DataView, offset: number, value: number) {
  const v = Math.max(0, Math.trunc(value));
  view.setUint32(offset, v >>> 0, true);
  view.setUint32(offset + 4, Math.floor(v / 0x1_0000_0000), true);
}

function readU64(view: DataView, offset: number): number {
  const lo = view.getUint32(offset, true);
  const hi = view.getUint32(offset + 4, true);
  return hi * 0x1_0000_0000 + lo;
}

function asFloat64(arr: number[] | Float32Array): Float32Array {
  if (arr instanceof Float32Array) return arr;
  const out = new Float32Array(CL1_TOTAL_CHANNELS);
  for (let i = 0; i < CL1_TOTAL_CHANNELS; i += 1) out[i] = arr[i] ?? 0;
  return out;
}

export function packStimPacket(
  timestampUs: number,
  frequencies: number[] | Float32Array,
  amplitudes: number[] | Float32Array
): ArrayBuffer {
  const buf = new ArrayBuffer(CL1_STIM_PACKET_SIZE);
  const view = new DataView(buf);
  writeU64(view, 0, timestampUs);

  const freqs = asFloat64(frequencies);
  const amps = asFloat64(amplitudes);
  let o = 8;
  for (let i = 0; i < CL1_TOTAL_CHANNELS; i += 1) {
    view.setFloat32(o, freqs[i], true);
    o += 4;
  }
  for (let i = 0; i < CL1_TOTAL_CHANNELS; i += 1) {
    view.setFloat32(o, amps[i], true);
    o += 4;
  }
  return buf;
}

export function unpackStimPacket(buf: ArrayBuffer): {
  timestampUs: number;
  frequencies: Float32Array;
  amplitudes: Float32Array;
} {
  if (buf.byteLength !== CL1_STIM_PACKET_SIZE) {
    throw new Error(`STIM packet must be ${CL1_STIM_PACKET_SIZE} bytes, got ${buf.byteLength}`);
  }
  const view = new DataView(buf);
  const timestampUs = readU64(view, 0);
  const frequencies = new Float32Array(CL1_TOTAL_CHANNELS);
  const amplitudes = new Float32Array(CL1_TOTAL_CHANNELS);
  let o = 8;
  for (let i = 0; i < CL1_TOTAL_CHANNELS; i += 1) {
    frequencies[i] = view.getFloat32(o, true);
    o += 4;
  }
  for (let i = 0; i < CL1_TOTAL_CHANNELS; i += 1) {
    amplitudes[i] = view.getFloat32(o, true);
    o += 4;
  }
  return { timestampUs, frequencies, amplitudes };
}

export function packSpikePacket(timestampUs: number, spikeCounts: number[] | Float32Array): ArrayBuffer {
  const buf = new ArrayBuffer(CL1_SPIKE_PACKET_SIZE);
  const view = new DataView(buf);
  writeU64(view, 0, timestampUs);
  const counts = asFloat64(spikeCounts);
  let o = 8;
  for (let i = 0; i < CL1_TOTAL_CHANNELS; i += 1) {
    view.setFloat32(o, counts[i], true);
    o += 4;
  }
  return buf;
}

export function unpackSpikePacket(buf: ArrayBuffer): { timestampUs: number; spikeCounts: Float32Array } {
  if (buf.byteLength !== CL1_SPIKE_PACKET_SIZE) {
    throw new Error(`SPIKE packet must be ${CL1_SPIKE_PACKET_SIZE} bytes, got ${buf.byteLength}`);
  }
  const view = new DataView(buf);
  const timestampUs = readU64(view, 0);
  const spikeCounts = new Float32Array(CL1_TOTAL_CHANNELS);
  let o = 8;
  for (let i = 0; i < CL1_TOTAL_CHANNELS; i += 1) {
    spikeCounts[i] = view.getFloat32(o, true);
    o += 4;
  }
  return { timestampUs, spikeCounts };
}
