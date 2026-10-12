import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  status: number;
  code: string;
  details: { field: string; message: string }[];

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.message || fallback);
    this.status = status;
    this.code = body?.code || "error";
    this.details = body?.details || [];
  }
}

function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/(?:^|; )esim_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function withSession(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init?.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  return { ...init, headers, cache: "no-store", credentials: "include" };
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, withSession(init));
  if (!response.ok) {
    let body: { error?: ApiErrorBody } | null = null;
    try {
      body = (await response.json()) as { error?: ApiErrorBody };
    } catch {
      body = null;
    }
    throw new ApiError(response.status, body?.error ?? null, response.statusText || "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await fetch(`/api/v1${path}`, withSession());
  if (!response.ok) {
    let body: { error?: ApiErrorBody } | null = null;
    try {
      body = (await response.json()) as { error?: ApiErrorBody };
    } catch {
      body = null;
    }
    throw new ApiError(response.status, body?.error ?? null, "Download failed");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
