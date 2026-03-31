import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { Play, ChevronRight, Clock, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useRunStage, getListProjectStagesQueryKey, StageName, StageStatus, type StageOutput } from "@workspace/api-client-react";
import { cn } from "@/lib/utils";

const STAGE_META: Record<string, { label: string; description: string; order: number }> = {
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

interface StageCardProps {
  projectId: number;
  stage: StageOutput;
  canRun: boolean;
}

export function StageCard({ projectId, stage, canRun }: StageCardProps) {
  const queryClient = useQueryClient();
  const [runError, setRunError] = useState<string | null>(null);

  const meta = STAGE_META[stage.stage] ?? {
    label: stage.stage,
    description: "",
    order: 99,
  };

  const { mutate: runStage, isPending } = useRunStage({
    mutation: {
      onSuccess: () => {
        setRunError(null);
        queryClient.invalidateQueries({ queryKey: getListProjectStagesQueryKey(projectId) });
      },
      onError: (err: any) => {
        const msg = err?.body?.message ?? err?.message ?? "Stage run failed";
        setRunError(msg);
        queryClient.invalidateQueries({ queryKey: getListProjectStagesQueryKey(projectId) });
      },
    },
  });

  const isRunning = stage.status === StageStatus.running || isPending;
  const isComplete = stage.status === StageStatus.complete;
  const isFailed = stage.status === StageStatus.failed;

  function handleRun() {
    setRunError(null);
    runStage({ id: projectId, stage: stage.stage as StageName });
  }

  return (
    <div className={cn(
      "border rounded-sm bg-card transition-colors",
      isRunning && "border-blue-200 bg-blue-50/30",
      isFailed && "border-red-200",
      isComplete && "border-green-100",
      !isRunning && !isFailed && !isComplete && "border-border",
    )}>
      <div className="flex items-start gap-4 p-4">
        {/* Order number */}
        <div className={cn(
          "w-7 h-7 flex-shrink-0 rounded-sm border flex items-center justify-center text-xs font-mono font-bold",
          isComplete ? "bg-green-50 border-green-200 text-green-700" :
          isFailed ? "bg-red-50 border-red-200 text-red-600" :
          isRunning ? "bg-blue-50 border-blue-200 text-blue-600" :
          "bg-muted border-border text-muted-foreground"
        )}>
          {meta.order}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-foreground">{meta.label}</h3>
            <StatusBadge status={isRunning ? "running" : stage.status} size="xs" />
          </div>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            {meta.description}
          </p>

          {/* Error message */}
          {(isFailed || runError) && (
            <div className="mt-2 flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-destructive mt-0.5 flex-shrink-0" />
              <p className="text-xs text-destructive font-mono leading-relaxed">
                {stage.errorMessage ?? runError ?? "Unknown error"}
              </p>
            </div>
          )}

          {/* Completion time */}
          {isComplete && stage.updatedAt && (
            <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground">
              <CheckCircle2 className="w-3 h-3 text-green-600" />
              <span>Completed {new Date(stage.updatedAt).toLocaleString()}</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {isComplete && (
            <Link href={`/projects/${projectId}/stage/${stage.stage}`}>
              <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
                Output
                <ChevronRight className="w-3 h-3" />
              </Button>
            </Link>
          )}
          <Button
            size="sm"
            variant={isComplete ? "outline" : "default"}
            className="h-7 text-xs gap-1.5"
            onClick={handleRun}
            disabled={isRunning || !canRun}
            title={!canRun ? "Complete earlier stages first" : undefined}
          >
            {isRunning ? (
              <>
                <Clock className="w-3 h-3 animate-spin" />
                Running…
              </>
            ) : isComplete ? (
              <>
                <Play className="w-3 h-3" />
                Re-run
              </>
            ) : (
              <>
                <Play className="w-3 h-3" />
                Run
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
