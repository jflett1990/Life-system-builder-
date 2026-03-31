export const PIPELINE_STAGES = [
  "system-architecture",
  "document-outline",
  "chapter-expansion",
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
    label: "System Architecture",
    description: "Maps the life event into a named operational control system — domains, roles, milestones, and success criteria.",
    order: 1,
    modelRole: "planner",
  },
  "document-outline": {
    label: "Document Outline",
    description: "Produces the complete master blueprint — every chapter title, every worksheet title, the cascade chain, and master operating rules.",
    order: 2,
    modelRole: "planner",
  },
  "chapter-expansion": {
    label: "Chapter Expansion",
    description: "Expands each chapter independently — full narrative, all worksheets with fields, sections, and decision gates. One focused call per chapter.",
    order: 3,
    modelRole: "executor",
  },
  "layout-mapping": {
    label: "Layout Mapping",
    description: "Maps all chapters and worksheets into a structured document layout with section ordering and print architecture.",
    order: 4,
    modelRole: "executor",
  },
  "render-blueprint": {
    label: "Render Blueprint",
    description: "Produces the render instruction set — component directives, CSS tokens, and print specifications for the HTML engine.",
    order: 5,
    modelRole: "executor",
  },
  "validation-audit": {
    label: "Validation Audit",
    description: "Compiler-style structural audit — checks cross-stage references, field completeness, and render-readiness.",
    order: 6,
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
