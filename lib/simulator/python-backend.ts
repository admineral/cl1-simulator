import { NextResponse } from "next/server";

function isLocalUrl(url: string) {
  try {
    const u = new URL(url);
    return u.hostname === "127.0.0.1" || u.hostname === "localhost" || u.hostname === "::1";
  } catch {
    return true;
  }
}

function isPythonBackendEnabled() {
  if (process.env.CL_SIM_BACKEND !== "python") {
    return false;
  }
  // Vercel (and similar) cannot reach a laptop-local Python service unless you point at a public URL.
  if (process.env.VERCEL === "1") {
    const url = process.env.CL_SIM_PYTHON_URL ?? "http://127.0.0.1:8765";
    if (isLocalUrl(url)) {
      return false;
    }
  }
  return true;
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
