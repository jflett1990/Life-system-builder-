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
    description: "Interprets the tutorial request into a clear goal, audience fit, prerequisites, and success targets.",
    order: 1,
    modelRole: "planner",
  },
  "document-outline": {
    label: "Tutorial Outline",
    description: "Builds the walkthrough module map, milestones, and chapter-level learning flow.",
    order: 2,
    modelRole: "planner",
  },
  "chapter-expansion": {
    label: "Tutorial Detail Mapping",
    description: "Expands each module with implementation detail, checkpoints, debugging notes, and practical execution guidance.",
    order: 3,
    modelRole: "executor",
  },
  "chapter-worksheets": {
    label: "Code & Exercise Assets",
    description: "Generates worksheets, checklists, and structured practice/code artifacts that support each tutorial module.",
    order: 4,
    modelRole: "executor",
  },
  "appendix-builder": {
    label: "Reference & Debugging Pack",
    description: "Builds glossary, troubleshooting triggers, and practical reference resources for follow-through.",
    order: 5,
    modelRole: "executor",
  },
  "layout-mapping": {
    label: "Delivery Layout Mapping",
    description: "Maps tutorial content into structured sections for preview/export with ordered print-ready architecture.",
    order: 6,
    modelRole: "executor",
  },
  "render-blueprint": {
    label: "Render Blueprint",
    description: "Produces final rendering instructions, design tokens, and page composition rules for tutorial delivery.",
    order: 7,
    modelRole: "executor",
  },
  "validation-audit": {
    label: "Validation Audit",
    description: "Compiler-style structural audit for section completeness, cross-stage consistency, and render readiness.",
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
