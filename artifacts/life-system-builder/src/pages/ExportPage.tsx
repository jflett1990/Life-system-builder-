import { useQuery } from "@tanstack/react-query";
import { useParams } from "wouter";
import {
  getGetProjectQueryOptions,
  getListProjectStagesQueryOptions,
  getExportProjectQueryOptions,
  type ProjectWithStages,
} from "@workspace/api-client-react";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { ProjectHeader } from "@/components/layout/ProjectHeader";
import { Button } from "@/components/ui/button";
import { Download, FileCode, FileText, RefreshCw } from "lucide-react";

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const { data: project, isLoading: projectLoading } = useQuery(getGetProjectQueryOptions(projectId));
  const { data: stages } = useQuery(getListProjectStagesQueryOptions(projectId));
  const {
    data: exportBundle,
    isLoading: exportLoading,
    error: exportError,
    refetch,
  } = useQuery(getExportProjectQueryOptions(projectId));

  const isLoading = projectLoading || exportLoading;

  if (projectLoading) return <LoadingState message="Loading project…" />;
  if (!project) return <ErrorState title="Project not found" />;

  const projectWithStages: ProjectWithStages = { ...project, stages: stages ?? [] };

  const slug = project.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  function handleDownloadHtml() {
    if (!exportBundle) return;
    downloadFile(exportBundle.html, `${slug}-operational-system.html`, "text/html");
  }

  function handleDownloadJson() {
    if (!exportBundle) return;
    downloadFile(
      JSON.stringify(exportBundle.stagesJson, null, 2),
      `${slug}-stages.json`,
      "application/json"
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ProjectHeader project={projectWithStages} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Section header */}
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Export Bundle
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Download the complete operational system as self-contained files.
            </p>
          </div>

          {exportLoading && <LoadingState message="Building export bundle…" />}

          {exportError && (
            <div className="space-y-3">
              <div className="border border-amber-200 bg-amber-50 rounded-sm p-3">
                <p className="text-xs text-amber-700">
                  Export bundle could not be generated. Complete all pipeline stages first.
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-1.5 text-xs h-8">
                <RefreshCw className="w-3.5 h-3.5" />
                Retry
              </Button>
            </div>
          )}

          {exportBundle && (
            <div className="space-y-3">
              {/* Export metadata */}
              <div className="border rounded-sm p-4 bg-muted/20 space-y-1.5">
                <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">Bundle Info</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">Project: </span>
                    <span className="font-medium">{project.title}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Exported: </span>
                    <span className="font-mono">{new Date(exportBundle.exportedAt).toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">HTML size: </span>
                    <span className="font-mono">{Math.round(exportBundle.html.length / 1024)} KB</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Stages JSON: </span>
                    <span className="font-mono">{Object.keys(exportBundle.stagesJson).length} stages</span>
                  </div>
                </div>
              </div>

              {/* Download cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="border rounded-sm p-4 bg-card space-y-3">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <div className="text-xs font-semibold text-foreground">HTML Document</div>
                      <div className="text-[10px] text-muted-foreground">Self-contained, print-ready</div>
                    </div>
                  </div>
                  <Button size="sm" className="w-full gap-1.5 text-xs h-8" onClick={handleDownloadHtml}>
                    <Download className="w-3.5 h-3.5" />
                    Download HTML
                  </Button>
                </div>

                <div className="border rounded-sm p-4 bg-card space-y-3">
                  <div className="flex items-center gap-2">
                    <FileCode className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <div className="text-xs font-semibold text-foreground">Stage Outputs</div>
                      <div className="text-[10px] text-muted-foreground">Structured JSON data</div>
                    </div>
                  </div>
                  <Button size="sm" variant="outline" className="w-full gap-1.5 text-xs h-8" onClick={handleDownloadJson}>
                    <Download className="w-3.5 h-3.5" />
                    Download JSON
                  </Button>
                </div>
              </div>

              {/* Refresh */}
              <div className="flex justify-end">
                <Button variant="ghost" size="sm" onClick={() => refetch()} className="gap-1.5 text-xs h-7 text-muted-foreground">
                  <RefreshCw className="w-3 h-3" />
                  Refresh bundle
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
