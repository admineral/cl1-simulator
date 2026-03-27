import { NextResponse } from "next/server";

function isPythonBackendEnabled() {
  return process.env.CL_SIM_BACKEND === "python";
}

function pythonBackendBaseUrl() {
  return process.env.CL_SIM_PYTHON_URL ?? "http://127.0.0.1:8765";
}

export function usePythonBackend() {
  return isPythonBackendEnabled();
}

export async function proxyPythonSimulator(
  pathname: string,
  init?: {
    method?: "GET" | "POST";
    body?: string;
  }
) {
  const response = await fetch(`${pythonBackendBaseUrl()}${pathname}`, {
    method: init?.method ?? "GET",
    cache: "no-store",
    headers:
      init?.method === "POST"
        ? {
            "Content-Type": "application/json"
          }
        : undefined,
    body: init?.body
  });

  const json = await response.json().catch(() => ({
    error: `Python simulator request failed with ${response.status}`
  }));

  return NextResponse.json(json, { status: response.status });
}
