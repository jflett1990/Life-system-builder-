import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "wouter";
import { useState } from "react";
import {
  getGetProjectQueryOptions,
  getListProjectStagesQueryOptions,
  getListProjectStagesQueryKey,
  useRunStage,
  StageName,
  StageStatus,
  type StageOutput,
} from "@workspace/api-client-react";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { ProjectHeader } from "@/components/layout/ProjectHeader";
import { StageCard } from "@/components/pipeline/StageCard";
import { Button } from "@/components/ui/button";
import { Play, Pause } from "lucide-react";
import type { ProjectWithStages } from "@workspace/api-client-react";

const PIPELINE_STAGES: StageName[] = [
  "system-architecture",
  "worksheet-system",
  "layout-mapping",
  "render-blueprint",
  "validation-audit",
];

function getStageOrder(stageName: string): number {
  return PIPELINE_STAGES.indexOf(stageName as StageName);
}

function canRunStage(stages: StageOutput[], stageName: string): boolean {
  const idx = PIPELINE_STAGES.indexOf(stageName as StageName);
  if (idx <= 0) return true;
  const prevStage = PIPELINE_STAGES[idx - 1];
  const prev = stages.find((s) => s.stage === prevStage);
  return prev?.status === StageStatus.complete;
}

export default function PipelinePage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const queryClient = useQueryClient();
  const [runningAll, setRunningAll] = useState(false);

  const { data: project, isLoading: projectLoading, error: projectError } = useQuery(
    getGetProjectQueryOptions(projectId)
  );

  const { data: stages, isLoading: stagesLoading } = useQuery(
    getListProjectStagesQueryOptions(projectId)
  );

  const { mutateAsync: runStageAsync } = useRunStage({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListProjectStagesQueryKey(projectId) });
      },
    },
  });

  async function handleRunAll() {
    if (!stages) return;
    setRunningAll(true);
    try {
      for (const stageName of PIPELINE_STAGES) {
        const existing = stages.find((s) => s.stage === stageName);
        if (existing?.status === StageStatus.complete) continue;
        await runStageAsync({ id: projectId, stage: stageName });
        await queryClient.invalidateQueries({ queryKey: getListProjectStagesQueryKey(projectId) });
      }
    } finally {
      setRunningAll(false);
      queryClient.invalidateQueries({ queryKey: getListProjectStagesQueryKey(projectId) });
    }
  }

  const isLoading = projectLoading || stagesLoading;

  if (isLoading) return <LoadingState message="Loading project…" className="flex-1" />;
  if (projectError) return <ErrorState title="Project not found" />;
  if (!project) return null;

  const projectWithStages: ProjectWithStages = {
    ...project,
    stages: stages ?? [],
  };

  const orderedStages = PIPELINE_STAGES.map((name) => {
    const existing = stages?.find((s) => s.stage === name);
    return (
      existing ?? {
        id: 0,
        projectId,
        stage: name,
        status: StageStatus.pending,
        outputJson: {},
        validationResult: null,
        errorMessage: null,
        createdAt: "",
        updatedAt: "",
      }
    ) as StageOutput;
  });

  const allComplete = orderedStages.every((s) => s.status === StageStatus.complete);
  const anyRunning = orderedStages.some((s) => s.status === StageStatus.running);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ProjectHeader project={projectWithStages} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Controls */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Pipeline Stages
              </h2>
              <p className="text-xs text-muted-foreground">
                Run stages sequentially to generate the operational system.
              </p>
            </div>
            <Button
              size="sm"
              className="gap-1.5 text-xs h-8"
              onClick={handleRunAll}
              disabled={runningAll || anyRunning || allComplete}
              variant={allComplete ? "outline" : "default"}
            >
              {runningAll || anyRunning ? (
                <>
                  <Pause className="w-3.5 h-3.5 animate-pulse" />
                  Running…
                </>
              ) : allComplete ? (
                <>
                  <Play className="w-3.5 h-3.5" />
                  Re-run All
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  Run All
                </>
              )}
            </Button>
          </div>

          {/* Stage cards */}
          <div className="space-y-3">
            {orderedStages.map((stage) => (
              <StageCard
                key={stage.stage}
                projectId={projectId}
                stage={stage}
                canRun={canRunStage(orderedStages, stage.stage)}
              />
            ))}
          </div>

          {/* Pipeline context */}
          {project.context && (
            <div className="mt-6 border rounded-sm p-4 bg-muted/20">
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Project Context
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{project.context}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
