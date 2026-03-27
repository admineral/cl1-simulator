import { NextResponse } from "next/server";
import { simulator } from "@/lib/simulator/core";
import { packSpikePacket, packStimPacket } from "@/lib/simulator/packets";
import { proxyPythonSimulator, usePythonBackend } from "@/lib/simulator/python-backend";

export const dynamic = "force-dynamic";

/** Last-tick CL1-style STIM/SPIKE binary (520 B / 264 B) for integration / mock testing. */
export async function GET() {
  if (usePythonBackend()) {
    return proxyPythonSimulator("/simulator/device");
  }
  const { cl1 } = simulator.getSnapshot();
  const stimBuf = packStimPacket(cl1.stimTimestampUs, cl1.frequencies, cl1.amplitudes);
  const spikeBuf = packSpikePacket(cl1.spikeTimestampUs, cl1.spikeCounts);
  const toB64 = (b: ArrayBuffer) => Buffer.from(b).toString("base64");

  return NextResponse.json({
    cl1,
    stimPacketBase64: toB64(stimBuf),
    spikePacketBase64: toB64(spikeBuf),
    stimPacketSize: stimBuf.byteLength,
    spikePacketSize: spikeBuf.byteLength
  });
}
