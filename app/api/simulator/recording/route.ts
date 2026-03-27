import { mkdir, writeFile } from "fs/promises";
import path from "path";
import { NextRequest, NextResponse } from "next/server";
import { simulator } from "@/lib/simulator/core";
import { proxyPythonSimulator, usePythonBackend } from "@/lib/simulator/python-backend";
import { summarizeActivity } from "@/lib/simulator/serialization";

export const dynamic = "force-dynamic";

function safeBasename(s: string) {
  return s.replace(/[^a-z0-9-_]+/gi, "_").slice(0, 48) || "session";
}

export async function POST(request: NextRequest) {
  const rawBody = await request.text();

  if (usePythonBackend()) {
    return proxyPythonSimulator("/simulator/recording", {
      method: "POST",
      body: rawBody
    });
  }

  const body = ((rawBody ? JSON.parse(rawBody) : {}) ?? {}) as {
    action?: "start" | "stop";
    session?: string;
    persist?: boolean;
  };

  try {
    if (body.action === "start") {
      const snapshot = simulator.startRecording(body.session ?? "");
      return NextResponse.json(summarizeActivity(snapshot));
    }

    if (body.action === "stop") {
      const result = simulator.stopRecording();
      const summary = summarizeActivity(simulator.getSnapshot());

      let savedPath: string | undefined;
      if (body.persist && result.frames.length > 0) {
        const dir = path.join(process.cwd(), "recordings");
        await mkdir(dir, { recursive: true });
        const base = safeBasename(result.session ?? "export");
        const file = path.join(dir, `${base}-${Date.now()}.json`);
        await writeFile(
          file,
          JSON.stringify(
            {
              session: result.session,
              exportedAt: new Date().toISOString(),
              frameCount: result.frames.length,
              frames: result.frames
            },
            null,
            2
          ),
          "utf8"
        );
        savedPath = file;
      }

      return NextResponse.json({ ...summary, recordingExport: { savedPath, frameCount: result.frames.length } });
    }

    return NextResponse.json({ error: "action must be start or stop." }, { status: 400 });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Recording request failed." },
      { status: 400 }
    );
  }
}
