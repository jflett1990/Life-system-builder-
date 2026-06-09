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

export const PIPELINE_STAGE_COUNT = PIPELINE_STAGES.length;

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
    description:
      "Interprets the tutorial request — goal, audience, prerequisites, stack, constraints, and learning outcomes.",
    order: 1,
    modelRole: "planner",
  },
  "document-outline": {
    label: "Tutorial Outline",
    description:
      "Generates the major modules and steps — setup, milestones, learning flow, and checkpoint structure.",
    order: 2,
    modelRole: "planner",
  },
  "chapter-expansion": {
    label: "Step Detail Mapping",
    description:
      "Expands each module with implementation details, substeps, code examples, and verification checkpoints.",
    order: 3,
    modelRole: "executor",
  },
  "chapter-worksheets": {
    label: "Implementation Examples",
    description:
      "Produces hands-on exercises, code snippets, command references, and fill-in worksheets per module.",
    order: 4,
    modelRole: "executor",
  },
  "appendix-builder": {
    label: "Reference & Troubleshooting",
    description:
      "Builds glossary, common mistakes, debugging notes, and resource references specific to the tutorial topic.",
    order: 5,
    modelRole: "executor",
  },
  "layout-mapping": {
    label: "Delivery Layout",
    description:
      "Maps tutorial sections into a structured document layout optimized for reading and printing.",
    order: 6,
    modelRole: "executor",
  },
  "render-blueprint": {
    label: "Render Blueprint",
    description:
      "Produces the final render manifest — typography, code block styling, and page structure for export.",
    order: 7,
    modelRole: "executor",
  },
  "validation-audit": {
    label: "Validation Audit",
    description:
      "Checks structural completeness — prerequisites, step dependencies, code coverage, and render-readiness.",
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
