import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "wouter";
import {
  getGetStageOutputQueryOptions,
  StageName,
} from "@workspace/api-client-react";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { ProjectHeader } from "@/components/layout/ProjectHeader";
import { JsonViewer } from "@/components/output/JsonViewer";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getStageLabel } from "@/lib/stages";
import { useProjectWithStages } from "@/hooks/use-project";

export default function StagePage() {
  const { id, stage } = useParams<{ id: string; stage: string }>();
  const projectId = Number(id);

  const { projectWithStages, isLoading: projectLoading } = useProjectWithStages(projectId);
  const {
    data: stageOutput,
    isLoading: stageLoading,
    error: stageError,
  } = useQuery(getGetStageOutputQueryOptions(projectId, stage as StageName));

  const isLoading = projectLoading || stageLoading;

  if (isLoading) return <LoadingState message="Loading stage output…" />;
  if (!projectWithStages) return <ErrorState title="Project not found" />;

  const revisionNumber =
    (stageOutput as any)?.revisionNumber ?? (stageOutput as any)?.revision_number;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ProjectHeader project={projectWithStages} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {/* Sub-header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Link href={`/projects/${projectId}`}>
                <Button variant="ghost" size="sm" className="gap-1 h-7 text-xs px-2">
                  <ArrowLeft className="w-3 h-3" />
                  Pipeline
                </Button>
              </Link>
              <span className="text-muted-foreground/50">/</span>
              <span className="text-xs font-medium text-foreground">
                {getStageLabel(stage)}
              </span>
            </div>
            {stageOutput && (
              <div className="flex items-center gap-2">
                {revisionNumber != null && revisionNumber > 0 && (
                  <span className="text-[10px] font-mono text-muted-foreground">
                    rev {revisionNumber}
                  </span>
                )}
                <StatusBadge status={stageOutput.status} size="sm" />
              </div>
            )}
          </div>

          {stageError && (
            <ErrorState
              title="Stage output not available"
              message="This stage has not been run yet, or its output could not be loaded."
            />
          )}

          {stageOutput && (
            <>
              {/* Meta row */}
              {stageOutput.updatedAt && (
                <div className="flex flex-wrap items-center gap-4 text-[10px] font-mono text-muted-foreground border-b pb-3">
                  <span>
                    Stage: <span className="text-foreground">{getStageLabel(stageOutput.stage)}</span>
                  </span>
                  <span>
                    Status: <span className="text-foreground">{stageOutput.status}</span>
                  </span>
                  <span>
                    Updated: <span className="text-foreground">{new Date(stageOutput.updatedAt).toLocaleString()}</span>
                  </span>
                  {revisionNumber != null && revisionNumber > 0 && (
                    <span>
                      Revision: <span className="text-foreground">{revisionNumber}</span>
                    </span>
                  )}
                </div>
              )}

              {/* Error */}
              {stageOutput.errorMessage && (
                <div className="border border-destructive/20 bg-destructive/5 rounded-sm p-3">
                  <div className="text-[9px] font-mono uppercase tracking-wider text-destructive mb-1">Error</div>
                  <p className="text-xs font-mono text-destructive">{stageOutput.errorMessage}</p>
                </div>
              )}

              {/* JSON Output */}
              {stageOutput.outputJson && Object.keys(stageOutput.outputJson).length > 0 ? (
                <JsonViewer data={stageOutput.outputJson} />
              ) : (
                <div className="border rounded-sm p-6 bg-muted/20 text-center">
                  <p className="text-xs text-muted-foreground">No output data for this stage.</p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
