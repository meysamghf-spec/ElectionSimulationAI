const DRAFT_KEY = "esim.draft.v1";

import type { ElectionSpecification } from "./types";

export function loadDraft(): ElectionSpecification | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(DRAFT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ElectionSpecification;
  } catch {
    return null;
  }
}

export function saveDraft(spec: ElectionSpecification): void {
  window.localStorage.setItem(DRAFT_KEY, JSON.stringify(spec));
}

export function clearDraft(): void {
  window.localStorage.removeItem(DRAFT_KEY);
}
