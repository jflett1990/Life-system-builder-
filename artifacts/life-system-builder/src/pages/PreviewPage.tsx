import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "wouter";
import {
  getGetProjectQueryOptions,
  getListProjectStagesQueryOptions,
  useRenderProject,
  type ProjectWithStages,
} from "@workspace/api-client-react";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { ProjectHeader } from "@/components/layout/ProjectHeader";
import { DocumentFrame } from "@/components/preview/DocumentFrame";
import { Button } from "@/components/ui/button";
import { FileText, RefreshCw } from "lucide-react";

export default function PreviewPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [renderResult, setRenderResult] = useState<{ html: string; pageCount: number } | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  const { data: project, isLoading: projectLoading } = useQuery(getGetProjectQueryOptions(projectId));
  const { data: stages } = useQuery(getListProjectStagesQueryOptions(projectId));

  const { mutate: render, isPending } = useRenderProject({
    mutation: {
      onSuccess: (data: any) => {
        setRenderResult({ html: data.html, pageCount: data.pageCount ?? data.page_count ?? 1 });
        setRenderError(null);
      },
      onError: (err: any) => {
        setRenderError(err?.body?.message ?? err?.message ?? "Render failed");
      },
    },
  });

  if (projectLoading) return <LoadingState message="Loading project…" />;
  if (!project) return <ErrorState title="Project not found" />;

  const projectWithStages: ProjectWithStages = { ...project, stages: stages ?? [] };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ProjectHeader project={projectWithStages} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-5">
          {/* Controls */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Document Preview
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Renders the operational system as a print-ready HTML document.
              </p>
            </div>
            <Button
              size="sm"
              className="gap-1.5 text-xs h-8"
              onClick={() => render({ id: projectId })}
              disabled={isPending}
            >
              {isPending ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Rendering…
                </>
              ) : renderResult ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5" />
                  Re-render
                </>
              ) : (
                <>
                  <FileText className="w-3.5 h-3.5" />
                  Render Document
                </>
              )}
            </Button>
          </div>

          {renderError && (
            <div className="border border-destructive/20 bg-destructive/5 rounded-sm p-3">
              <p className="text-xs text-destructive font-mono">{renderError}</p>
            </div>
          )}

          {!renderResult && !isPending && (
            <div className="flex flex-col items-center gap-4 py-20 border rounded-sm bg-muted/10 text-center">
              <FileText className="w-8 h-8 text-muted-foreground/30" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">No preview yet</p>
                <p className="text-xs text-muted-foreground max-w-sm">
                  Complete the pipeline stages first, then render the document to see the preview.
                </p>
              </div>
            </div>
          )}

          {isPending && <LoadingState message="Generating document…" />}

          {renderResult && !isPending && (
            <DocumentFrame
              html={renderResult.html}
              pageCount={renderResult.pageCount}
            />
          )}
        </div>
      </div>
    </div>
  );
}
