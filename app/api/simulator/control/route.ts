import { NextRequest, NextResponse } from "next/server";
import { simulator } from "@/lib/simulator/core";
import { proxyPythonSimulator, usePythonBackend } from "@/lib/simulator/python-backend";
import { summarizeActivity } from "@/lib/simulator/serialization";

type ControlAction = "start" | "stop" | "reset" | "tick";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rawBody = await request.text();

  if (usePythonBackend()) {
    return proxyPythonSimulator("/simulator/control", {
      method: "POST",
      body: rawBody
    });
  }

  const body = ((rawBody ? JSON.parse(rawBody) : {}) ?? {}) as {
    action?: ControlAction;
    tickIntervalMs?: number;
    neuronCount?: number;
  };

  const action = body.action ?? "tick";
  let snapshot;

  switch (action) {
    case "start":
      snapshot = simulator.start({
        tickIntervalMs: body.tickIntervalMs,
        neuronCount: body.neuronCount
      });
      break;
    case "stop":
      snapshot = simulator.stop();
      break;
    case "reset":
      snapshot = simulator.reset();
      break;
    case "tick":
      snapshot = simulator.tickOnce();
      break;
    default:
      return NextResponse.json(
        { error: `Unsupported action: ${String(action)}` },
        { status: 400 }
      );
  }

  return NextResponse.json(summarizeActivity(snapshot));
}
