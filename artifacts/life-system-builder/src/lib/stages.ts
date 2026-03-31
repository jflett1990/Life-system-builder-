export const PIPELINE_STAGES = [
  "system-architecture",
  "worksheet-system",
  "layout-mapping",
  "render-blueprint",
  "validation-audit",
] as const;

export type StageName = (typeof PIPELINE_STAGES)[number];

export interface StageMeta {
  label: string;
  description: string;
  order: number;
}

export const STAGE_META: Record<string, StageMeta> = {
  "system-architecture": {
    label: "System Architecture",
    description: "Maps the life event into a structural operating system with domains and roles.",
    order: 1,
  },
  "worksheet-system": {
    label: "Worksheet System",
    description: "Generates task worksheets, trackers, and checklists for each domain.",
    order: 2,
  },
  "layout-mapping": {
    label: "Layout Mapping",
    description: "Assigns document archetypes and page layout structures to each worksheet.",
    order: 3,
  },
  "render-blueprint": {
    label: "Render Blueprint",
    description: "Produces the final render manifest with page-level content and formatting.",
    order: 4,
  },
  "validation-audit": {
    label: "Validation Audit",
    description: "Runs compiler-style validation checks across all stage outputs.",
    order: 5,
  },
};

export function getStageMeta(stage: string): StageMeta {
  return (
    STAGE_META[stage] ??
    STAGE_META[stage.replace(/_/g, "-")] ?? {
      label: stage.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      description: "",
      order: 99,
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
