"use client";

import { useState } from "react";
import { loadDraft, saveDraft } from "@/lib/draft";
import type { ElectionSpecification } from "@/lib/types";

export function useDraft() {
  const [spec, setSpec] = useState<ElectionSpecification | null>(() => loadDraft());

  function update(next: ElectionSpecification | null) {
    setSpec(next);
    if (next) saveDraft(next);
  }

  return { spec, ready: true, update };
}
