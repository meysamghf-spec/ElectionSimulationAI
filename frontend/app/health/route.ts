import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Public health endpoint for the shared reverse proxy and uptime checks.
 * 200 when the web server is up and the API reports its database ready; 503 otherwise.
 * Returns no configuration, versions, or error text.
 */
export async function GET() {
  const base = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  let api = "unreachable";
  try {
    const response = await fetch(`${base}/api/v1/ready`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    api = response.ok ? "ok" : "not_ready";
  } catch {
    api = "unreachable";
  }
  const ok = api === "ok";
  return NextResponse.json(
    { status: ok ? "ok" : "degraded", web: "ok", api },
    { status: ok ? 200 : 503, headers: { "Cache-Control": "no-store" } },
  );
}
