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
import { Archive, Download, FileCode, FileText, RefreshCw } from "lucide-react";
import { getStageLabel } from "@/lib/stages";

function downloadBlob(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadFromUrl(path: string) {
  const base = import.meta.env.BASE_URL?.replace(/\/$/, "") ?? "";
  const a = document.createElement("a");
  a.href = `${base}${path}`;
  a.click();
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

  if (projectLoading) return <LoadingState message="Loading project…" />;
  if (!project) return <ErrorState title="Project not found" />;

  const projectWithStages: ProjectWithStages = { ...project, stages: stages ?? [] };
  const slug = project.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const completedStages = exportBundle ? Object.keys(exportBundle.stagesJson) : [];

  function handleDownloadHtml() {
    if (!exportBundle) return;
    downloadBlob(exportBundle.html, `${slug}-operational-system.html`, "text/html");
  }

  function handleDownloadJson() {
    if (!exportBundle) return;
    downloadBlob(
      JSON.stringify(exportBundle.stagesJson, null, 2),
      `${slug}-stages.json`,
      "application/json",
    );
  }

  function handleDownloadZip() {
    downloadFromUrl(`/api/export/${projectId}/download`);
  }

  function handleDownloadStageJson(stage: string) {
    downloadFromUrl(`/api/export/${projectId}/json/${stage}`);
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ProjectHeader project={projectWithStages} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">

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
                <p className="text-xs text-amber-800 font-medium mb-0.5">Export unavailable</p>
                <p className="text-xs text-amber-700">
                  Complete all pipeline stages before exporting. At least the system architecture
                  stage must be complete.
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-1.5 text-xs h-8">
                <RefreshCw className="w-3.5 h-3.5" />
                Retry
              </Button>
            </div>
          )}

          {exportBundle && (
            <div className="space-y-5">

              {/* Bundle metadata */}
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
                    <span className="text-muted-foreground">Stages: </span>
                    <span className="font-mono">{completedStages.length} completed</span>
                  </div>
                </div>
              </div>

              {/* Primary download — zip bundle */}
              <div className="border border-accent/40 rounded-sm p-4 bg-accent/5 space-y-3">
                <div className="flex items-start gap-2">
                  <Archive className="w-4 h-4 mt-0.5 text-accent shrink-0" />
                  <div>
                    <div className="text-xs font-semibold text-foreground">Complete Bundle (.zip)</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">
                      manifest.json · html/document.html · json/{"{stage}"}.json · pdf/PENDING.txt
                    </div>
                  </div>
                </div>
                <Button size="sm" className="w-full gap-1.5 text-xs h-8" onClick={handleDownloadZip}>
                  <Download className="w-3.5 h-3.5" />
                  Download Bundle
                </Button>
              </div>

              {/* Individual file downloads */}
              <div className="space-y-2">
                <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">Individual Files</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">

                  <div className="border rounded-sm p-4 bg-card space-y-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-muted-foreground" />
                      <div>
                        <div className="text-xs font-semibold text-foreground">HTML Document</div>
                        <div className="text-[10px] text-muted-foreground">Self-contained, print-ready</div>
                      </div>
                    </div>
                    <Button size="sm" variant="outline" className="w-full gap-1.5 text-xs h-8" onClick={handleDownloadHtml}>
                      <Download className="w-3.5 h-3.5" />
                      Download HTML
                    </Button>
                  </div>

                  <div className="border rounded-sm p-4 bg-card space-y-3">
                    <div className="flex items-center gap-2">
                      <FileCode className="w-4 h-4 text-muted-foreground" />
                      <div>
                        <div className="text-xs font-semibold text-foreground">All Stage Outputs</div>
                        <div className="text-[10px] text-muted-foreground">Combined JSON</div>
                      </div>
                    </div>
                    <Button size="sm" variant="outline" className="w-full gap-1.5 text-xs h-8" onClick={handleDownloadJson}>
                      <Download className="w-3.5 h-3.5" />
                      Download JSON
                    </Button>
                  </div>
                </div>
              </div>

              {/* Per-stage JSON downloads */}
              {completedStages.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">
                    Per-Stage JSON
                  </div>
                  <div className="border rounded-sm divide-y bg-card">
                    {completedStages.map((stage) => (
                      <div key={stage} className="flex items-center justify-between px-3 py-2">
                        <span className="text-xs text-foreground">{getStageLabel(stage)}</span>
                        <button
                          onClick={() => handleDownloadStageJson(stage)}
                          className="text-[10px] font-mono text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                          title={`Download ${stage}.json`}
                        >
                          <Download className="w-3 h-3" />
                          {stage}.json
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* PDF notice */}
              <div className="border border-dashed rounded-sm p-3 space-y-1">
                <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">Saving as PDF</div>
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  The HTML document includes Pagedjs — a print layout engine that runs in the browser.
                  Open it in Chrome or Edge, wait for the pagination to finish, then use{" "}
                  <span className="font-mono">File → Print → Save as PDF</span>.
                  This produces a WYSIWYG PDF with running page numbers and accurate page breaks.
                </p>
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
