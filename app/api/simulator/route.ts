import { NextResponse } from "next/server";
import { simulator } from "@/lib/simulator/core";
import { proxyPythonSimulator, usePythonBackend } from "@/lib/simulator/python-backend";
import { summarizeActivity } from "@/lib/simulator/serialization";

export const dynamic = "force-dynamic";

export async function GET() {
  if (usePythonBackend()) {
    return proxyPythonSimulator("/simulator");
  }
  return NextResponse.json(summarizeActivity(simulator.getSnapshot()));
}
