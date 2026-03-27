import { NextRequest, NextResponse } from "next/server";
import { simulator } from "@/lib/simulator/core";
import { proxyPythonSimulator, usePythonBackend } from "@/lib/simulator/python-backend";
import { summarizeActivity } from "@/lib/simulator/serialization";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rawBody = await request.text();

  if (usePythonBackend()) {
    return proxyPythonSimulator("/simulator/stim", {
      method: "POST",
      body: rawBody
    });
  }

  const body = ((rawBody ? JSON.parse(rawBody) : {}) ?? {}) as {
    channel?: number;
    channels?: number[];
    currentUa?: number;
    stimDesign?: {
      phases: {
        durationUs: number;
        currentUa: number;
      }[];
    };
    burstDesign?: {
      burstCount: number;
      burstHz: number;
    };
    leadTimeUs?: number;
  };

  try {
    const snapshot = simulator.triggerStim({
      channel: body.channel,
      channels: body.channels,
      currentUa: body.currentUa,
      stimDesign: body.stimDesign,
      burstDesign: body.burstDesign,
      leadTimeUs: body.leadTimeUs
    });

    return NextResponse.json(summarizeActivity(snapshot));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Stim request failed." },
      { status: 400 }
    );
  }
}
