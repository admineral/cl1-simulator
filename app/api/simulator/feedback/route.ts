import { NextRequest, NextResponse } from "next/server";
import { simulator } from "@/lib/simulator/core";
import { proxyPythonSimulator, usePythonBackend } from "@/lib/simulator/python-backend";
import { summarizeActivity } from "@/lib/simulator/serialization";
import type { FeedbackType } from "@/lib/simulator/types";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rawBody = await request.text();

  if (usePythonBackend()) {
    return proxyPythonSimulator("/simulator/feedback", {
      method: "POST",
      body: rawBody
    });
  }

  const body = ((rawBody ? JSON.parse(rawBody) : {}) ?? {}) as {
    feedbackType?: FeedbackType;
    channels?: number[];
    frequencyHz?: number;
    amplitudeUa?: number;
    pulses?: number;
    unpredictable?: boolean;
    eventName?: string;
  };

  try {
    if (!body.feedbackType || !Array.isArray(body.channels)) {
      return NextResponse.json(
        { error: "feedbackType and channels[] are required." },
        { status: 400 }
      );
    }

    const snapshot = simulator.enqueueFeedback({
      feedbackType: body.feedbackType,
      channels: body.channels,
      frequencyHz: body.frequencyHz,
      amplitudeUa: body.amplitudeUa,
      pulses: body.pulses,
      unpredictable: body.unpredictable,
      eventName: body.eventName
    });

    return NextResponse.json(summarizeActivity(snapshot));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Feedback request failed." },
      { status: 400 }
    );
  }
}
