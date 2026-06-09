export const PIPELINE_STAGES = [
  "system-architecture",
  "tutorial-research",
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
    description: "Interprets the request and frames the tutorial — goal, audience, prerequisites, stack, modules, milestones, and verifiable success criteria.",
    order: 1,
    modelRole: "planner",
  },
  "tutorial-research": {
    label: "Stack Research",
    description: "Grounds the tutorial in verifiable facts about the stack — version baselines, key commands with expected outputs, common errors with fixes, and canonical references.",
    order: 2,
    modelRole: "executor",
  },
  "document-outline": {
    label: "Tutorial Outline",
    description: "Produces the complete tutorial blueprint — every step title, every checkpoint and exercise sheet, the dependency chain, and ground rules.",
    order: 3,
    modelRole: "planner",
  },
  "chapter-expansion": {
    label: "Step Detail Writing",
    description: "Writes the full walkthrough for each step — numbered substeps, code snippets, expected outputs, decision points, and debugging notes. One focused call per step.",
    order: 4,
    modelRole: "executor",
  },
  "chapter-worksheets": {
    label: "Checkpoints & Exercises",
    description: "Generates verification checklists, command references, and exercises for each step using the walkthrough as context. One focused call per step.",
    order: 5,
    modelRole: "executor",
  },
  "appendix-builder": {
    label: "Reference Appendix",
    description: "Generates stack-specific appendix pages: a glossary of key terms, a 'when to get help' guide, a key resources table, and blank notes pages.",
    order: 6,
    modelRole: "executor",
  },
  "layout-mapping": {
    label: "Layout Mapping",
    description: "Maps all steps and checkpoint sheets into a structured document layout with section ordering and print architecture.",
    order: 7,
    modelRole: "executor",
  },
  "render-blueprint": {
    label: "Render Blueprint",
    description: "Produces the render instruction set — component directives, CSS tokens, and print specifications for the HTML engine.",
    order: 8,
    modelRole: "executor",
  },
  "validation-audit": {
    label: "Validation Audit",
    description: "Compiler-style structural audit — checks cross-stage references, section completeness, prerequisite ordering, and render-readiness.",
    order: 9,
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
