import { NextRequest, NextResponse } from "next/server";

import { clientAddressFromEdge } from "@/lib/clientAddress";

export const dynamic = "force-dynamic";

const HOP_BY_HOP = ["connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length", "host"];

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const base = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const target = `${base}/api/v1/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers(request.headers);
  for (const name of HOP_BY_HOP) headers.delete(name);
  headers.delete("authorization");
  const edgeAddress = clientAddressFromEdge(headers.get("x-forwarded-for"));
  headers.delete("x-forwarded-for");
  headers.delete("x-real-ip");
  headers.delete("forwarded");
  if (edgeAddress) headers.set("x-forwarded-for", edgeAddress);
  const serverToken = process.env.API_TOKEN;
  if (serverToken) headers.set("authorization", `Bearer ${serverToken}`);
  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }
  try {
    const response = await fetch(target, init);
    const outgoing = new Headers();
    response.headers.forEach((value, key) => {
      if (HOP_BY_HOP.includes(key.toLowerCase()) || key.toLowerCase() === "set-cookie") return;
      outgoing.append(key, value);
    });
    const next = new NextResponse(response.body, { status: response.status, headers: outgoing });
    const setCookie = (response.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie;
    const cookies = setCookie ? setCookie.call(response.headers) : [];
    for (const cookie of cookies) next.headers.append("set-cookie", cookie);
    return next;
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "unavailable",
          message: "The API is not reachable from the frontend server. Start the backend or set API_INTERNAL_URL.",
          details: [],
        },
      },
      { status: 503 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
