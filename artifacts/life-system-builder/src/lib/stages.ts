export const PIPELINE_STAGES = [
  "system-architecture",
  "document-outline",
  "chapter-expansion",
  "chapter-worksheets",
  "appendix-builder",
  "layout-mapping",
  "render-blueprint",
  "validation-audit",
] as const;

export type StageName = (typeof PIPELINE_STAGES)[number];

export interface StageMeta {
  label: string;
  description: string;
  order: number;
  modelRole: "planner" | "executor";
}

export const STAGE_META: Record<string, StageMeta> = {
  "system-architecture": {
    label: "Tutorial Framing",
    description: "Interprets the request into a concrete tutorial goal, learner profile, prerequisites, stack, constraints, and success criteria.",
    order: 1,
    modelRole: "planner",
  },
  "document-outline": {
    label: "Tutorial Outline",
    description: "Builds the learning path: major modules, setup flow, checkpoints, exercises, and the order of the walkthrough.",
    order: 2,
    modelRole: "planner",
  },
  "chapter-expansion": {
    label: "Tutorial Detail Mapping",
    description: "Expands each module with step-by-step implementation guidance, examples, checkpoints, and debugging notes.",
    order: 3,
    modelRole: "executor",
  },
  "chapter-worksheets": {
    label: "Exercises & Checklists",
    description: "Creates labs, checklists, code-review prompts, verification steps, and planning worksheets for each tutorial module.",
    order: 4,
    modelRole: "executor",
  },
  "appendix-builder": {
    label: "Reference Builder",
    description: "Generates glossaries, tool references, troubleshooting resources, and next-step extension ideas for the tutorial.",
    order: 5,
    modelRole: "executor",
  },
  "layout-mapping": {
    label: "Delivery Layout",
    description: "Maps tutorial modules, exercises, checkpoints, and references into a structured printable delivery format.",
    order: 6,
    modelRole: "executor",
  },
  "render-blueprint": {
    label: "Render Blueprint",
    description: "Produces component directives, CSS tokens, and print specifications for the final tutorial artifact.",
    order: 7,
    modelRole: "executor",
  },
  "validation-audit": {
    label: "Validation Audit",
    description: "Audits structural completeness, prerequisite consistency, tutorial flow, checkpoints, and render-readiness.",
    order: 8,
    modelRole: "executor",
  },
};

export function getStageMeta(stage: string): StageMeta {
  return (
    STAGE_META[stage] ??
    STAGE_META[stage.replace(/_/g, "-")] ?? {
      label: stage.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      description: "",
      order: 99,
      modelRole: "executor",
    }
  );
}

export function getStageLabel(stage: string): string {
  return getStageMeta(stage).label;
}

export function getStageOrder(stage: string): number {
  const idx = PIPELINE_STAGES.indexOf(stage.replace(/_/g, "-") as StageName);
  return idx >= 0 ? idx : 99;
}
