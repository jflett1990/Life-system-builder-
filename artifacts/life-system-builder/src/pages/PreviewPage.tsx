import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "wouter";
import {
  useRenderProject,
} from "@workspace/api-client-react";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { ProjectHeader } from "@/components/layout/ProjectHeader";
import { DocumentFrame } from "@/components/preview/DocumentFrame";
import { Button } from "@/components/ui/button";
import { FileText, RefreshCw, Clock } from "lucide-react";
import { extractApiError } from "@/lib/error";
import { useProjectWithStages } from "@/hooks/use-project";

export default function PreviewPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [renderResult, setRenderResult] = useState<{ html: string; pageCount: number } | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [lastRenderedAt, setLastRenderedAt] = useState<Date | null>(null);

  const { projectWithStages, isLoading: projectLoading } = useProjectWithStages(projectId);

  // Check for a cached render artifact — tells us if this project has been rendered before
  const { data: cachedInfo } = useQuery({
    queryKey: ["render-cache", projectId],
    queryFn: async () => {
      const res = await fetch(`/api/render/${projectId}`);
      if (!res.ok) return null;
      return res.json() as Promise<{ pageCount: number; documentTitle: string; updatedAt: string }>;
    },
    retry: false,
    staleTime: 60_000,
  });

  const { mutate: render, isPending } = useRenderProject({
    mutation: {
      onSuccess: (data: any) => {
        setRenderResult({ html: data.html, pageCount: data.pageCount ?? data.page_count ?? 1 });
        setRenderError(null);
        setLastRenderedAt(new Date());
      },
      onError: (err) => {
        setRenderError(extractApiError(err, "Render failed"));
      },
    },
  });

  if (projectLoading) return <LoadingState message="Loading project…" />;
  if (!projectWithStages) return <ErrorState title="Project not found" />;

  const hasExistingRender = cachedInfo !== null && cachedInfo !== undefined;

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
                {hasExistingRender && !renderResult && cachedInfo && (
                  <span className="ml-1 text-muted-foreground/60">
                    · Last rendered {new Date(cachedInfo.updatedAt).toLocaleDateString()}
                  </span>
                )}
                {lastRenderedAt && (
                  <span className="ml-1 text-muted-foreground/60">
                    · Rendered {lastRenderedAt.toLocaleTimeString()}
                  </span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {renderResult && (
                <span className="text-[10px] font-mono text-muted-foreground">
                  {renderResult.pageCount} page{renderResult.pageCount !== 1 ? "s" : ""}
                </span>
              )}
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
                <p className="text-sm font-medium text-foreground">
                  {hasExistingRender ? "Click to load preview" : "No preview yet"}
                </p>
                <p className="text-xs text-muted-foreground max-w-sm">
                  {hasExistingRender
                    ? `A render exists from ${new Date((cachedInfo as any).updatedAt).toLocaleDateString()}. Click Render Document to generate a fresh preview.`
                    : "Complete the pipeline stages first, then render the document to see the preview."}
                </p>
              </div>
              {hasExistingRender && (
                <div className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
                  <Clock className="w-3 h-3" />
                  {(cachedInfo as any)?.pageCount} pages · {(cachedInfo as any)?.documentTitle}
                </div>
              )}
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
