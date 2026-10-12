"use client";

import { PromptWorkbench } from "@/components/PromptWorkbench";

export default function PromptPage() {
  return (
    <PromptWorkbench
      heading="Prompt editor"
      intro="Unambiguous counts and percentages are parsed directly. If no language-model key is configured, interpretation stays in deterministic fallback mode and every inferred value is labeled."
    />
  );
}
