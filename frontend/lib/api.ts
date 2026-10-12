import type { ApiErrorBody } from "./types";
import { loadToken } from "./draft";

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

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = loadToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api/v1${path}`, { ...init, headers, cache: "no-store" });
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
  const headers = new Headers();
  const token = loadToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api/v1${path}`, { headers, cache: "no-store" });
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
