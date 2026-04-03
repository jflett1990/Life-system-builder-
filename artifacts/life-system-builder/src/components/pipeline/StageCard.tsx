import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { Play, ChevronRight, Clock, AlertCircle, CheckCircle2, RotateCcw, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useRunStage, getListProjectStagesQueryKey, StageName, StageStatus, type StageOutput } from "@workspace/api-client-react";
import { getStageMeta } from "@/lib/stages";
import { extractApiError } from "@/lib/error";
import { cn } from "@/lib/utils";

interface StageCardProps {
  projectId: number;
  stage: StageOutput;
  canRun: boolean;
}

export function StageCard({ projectId, stage, canRun }: StageCardProps) {
  const queryClient = useQueryClient();
  const [runError, setRunError] = useState<string | null>(null);

  const meta = getStageMeta(stage.stage);

  const { mutate: runStage, isPending } = useRunStage({
    mutation: {
      onSuccess: () => {
        setRunError(null);
        queryClient.invalidateQueries({ queryKey: getListProjectStagesQueryKey(projectId) });
      },
      onError: (err) => {
        setRunError(extractApiError(err, "Stage run failed"));
        queryClient.invalidateQueries({ queryKey: getListProjectStagesQueryKey(projectId) });
      },
    },
  });

  const isRunning = stage.status === StageStatus.running || isPending;
  const isComplete = stage.status === StageStatus.complete;
  const isFailed = stage.status === StageStatus.failed || stage.status === "schema_failed";

  const revisionNumber = (stage as any).revisionNumber ?? (stage as any).revision_number;

  // Chapter-level progress (chapter_expansion stage only)
  const subProgress = isRunning && stage.stage === "chapter-expansion"
    ? (stage as any).subProgress as { completed: number; total: number; currentDomains: string[] } | null | undefined
    : null;

  function handleRun(force = false) {
    setRunError(null);
    runStage({ id: projectId, stage: stage.stage as StageName, ...(force ? { force: true } : {}) });
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
            {revisionNumber > 1 && (
              <span className="text-[9px] font-mono text-muted-foreground/60">
                rev {revisionNumber}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            {meta.description}
          </p>

          {/* Chapter-level progress (chapter_expansion only) */}
          {subProgress && subProgress.total > 0 && (
            <div className="mt-2.5 space-y-1.5">
              <div className="flex items-center justify-between text-[10px] font-mono text-blue-700">
                <span className="flex items-center gap-1">
                  <Layers className="w-3 h-3" />
                  {subProgress.completed} / {subProgress.total} chapters
                </span>
                <span>{Math.round((subProgress.completed / subProgress.total) * 100)}%</span>
              </div>
              <div className="h-1 rounded-full bg-blue-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all duration-500"
                  style={{ width: `${(subProgress.completed / subProgress.total) * 100}%` }}
                />
              </div>
              {subProgress.currentDomains && subProgress.currentDomains.length > 0 && (
                <div className="space-y-0.5">
                  {subProgress.currentDomains.slice(0, 4).map((d, i) => (
                    <p key={i} className="text-[10px] text-blue-600/70 truncate flex items-center gap-1">
                      <span className="inline-block w-1 h-1 rounded-full bg-blue-400 flex-shrink-0 animate-pulse" />
                      {d}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {(isFailed || runError) && (
            <div className="mt-2 flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-destructive mt-0.5 flex-shrink-0" />
              <p className="text-xs text-destructive font-mono leading-relaxed">
                {stage.errorMessage ?? runError ?? "Unknown error"}
              </p>
            </div>
          )}

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

          {isComplete ? (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs gap-1.5"
              onClick={() => handleRun(true)}
              disabled={isRunning}
              title="Force re-run — generates fresh output"
            >
              <RotateCcw className="w-3 h-3" />
              Re-run
            </Button>
          ) : (
            <Button
              size="sm"
              variant={isFailed ? "destructive" : "default"}
              className="h-7 text-xs gap-1.5"
              onClick={() => handleRun(false)}
              disabled={isRunning || !canRun}
              title={!canRun ? "Complete earlier stages first" : undefined}
            >
              {isRunning ? (
                <>
                  <Clock className="w-3 h-3 animate-spin" />
                  Running…
                </>
              ) : (
                <>
                  <Play className="w-3 h-3" />
                  {isFailed ? "Retry" : "Run"}
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
