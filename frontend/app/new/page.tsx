"use client";

import { PromptWorkbench } from "@/components/PromptWorkbench";

export default function NewSimulationPage() {
  return (
    <PromptWorkbench
      heading="New simulation"
      intro="Describe the election in ordinary language. Interpreting the prompt saves a draft configuration. It does not start a simulation."
    />
  );
}
