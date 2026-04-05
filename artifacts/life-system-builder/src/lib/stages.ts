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
    description: "Writes the full narrative, quick-reference rules, and cascade triggers for each chapter. One focused call per chapter — no worksheets.",
    order: 3,
    modelRole: "executor",
  },
  "chapter-worksheets": {
    label: "Chapter Worksheets",
    description: "Generates all worksheets for each chapter using the chapter narrative as context. One focused call per chapter — no narrative writing.",
    order: 4,
    modelRole: "executor",
  },
  "appendix-builder": {
    label: "Appendix Builder",
    description: "Generates domain-specific appendix pages: a glossary of key terms, a situational guide for when to call a professional, a key resources table, and blank notes pages.",
    order: 5,
    modelRole: "executor",
  },
  "layout-mapping": {
    label: "Layout Mapping",
    description: "Maps all chapters and worksheets into a structured document layout with section ordering and print architecture.",
    order: 6,
    modelRole: "executor",
  },
  "render-blueprint": {
    label: "Render Blueprint",
    description: "Produces the render instruction set — component directives, CSS tokens, and print specifications for the HTML engine.",
    order: 7,
    modelRole: "executor",
  },
  "validation-audit": {
    label: "Validation Audit",
    description: "Compiler-style structural audit — checks cross-stage references, field completeness, and render-readiness.",
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
