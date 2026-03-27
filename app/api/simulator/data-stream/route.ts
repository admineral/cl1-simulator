import { NextRequest, NextResponse } from "next/server";
import { simulator } from "@/lib/simulator/core";
import { proxyPythonSimulator, usePythonBackend } from "@/lib/simulator/python-backend";
import { summarizeActivity } from "@/lib/simulator/serialization";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rawBody = await request.text();

  if (usePythonBackend()) {
    return proxyPythonSimulator("/simulator/data-stream", {
      method: "POST",
      body: rawBody
    });
  }

  const body = ((rawBody ? JSON.parse(rawBody) : {}) ?? {}) as {
    name?: string;
    data?: string;
    timestampUs?: number;
    attributes?: Record<string, string>;
  };

  try {
    const snapshot = simulator.appendDataStream({
      name: body.name ?? "",
      data: body.data ?? "",
      timestampUs: body.timestampUs,
      attributes: body.attributes
    });

    return NextResponse.json(summarizeActivity(snapshot));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Data stream request failed." },
      { status: 400 }
    );
  }
}
