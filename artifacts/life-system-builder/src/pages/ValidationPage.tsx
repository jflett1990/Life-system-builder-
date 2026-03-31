import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "wouter";
import {
  getGetProjectQueryOptions,
  getListProjectStagesQueryOptions,
  useValidateProject,
  type ProjectWithStages,
} from "@workspace/api-client-react";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { ProjectHeader } from "@/components/layout/ProjectHeader";
import { ValidationSummary } from "@/components/validation/ValidationSummary";
import { DefectList } from "@/components/validation/DefectList";
import { Button } from "@/components/ui/button";
import { ShieldCheck, RefreshCw } from "lucide-react";
import type { Defect } from "@/components/validation/DefectList";

interface RawValidationResult {
  verdict?: string;
  blocked_handoff?: boolean;
  defect_count?: number;
  defects?: Defect[];
  summary?: string;
  passed?: boolean;
  issueCount?: number;
  issues?: Array<{
    severity: string;
    field: string;
    stage: string;
    message: string;
  }>;
}

function parseDefects(result: RawValidationResult): Defect[] {
  if (result.defects?.length) return result.defects;
  if (result.issues?.length) {
    return result.issues.map((issue, i) => ({
      code: `ISSUE-${i + 1}`,
      severity: issue.severity,
      title: issue.message,
      message: issue.message,
      stage: issue.stage,
      field_path: issue.field,
    }));
  }
  return [];
}

export default function ValidationPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const queryClient = useQueryClient();
  const [validationResult, setValidationResult] = useState<RawValidationResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const { data: project, isLoading: projectLoading } = useQuery(getGetProjectQueryOptions(projectId));
  const { data: stages } = useQuery(getListProjectStagesQueryOptions(projectId));

  const { mutate: validate, isPending } = useValidateProject({
    mutation: {
      onSuccess: (data: any) => {
        setValidationResult(data as RawValidationResult);
        setRunError(null);
        queryClient.invalidateQueries({ queryKey: ["validation", projectId] });
      },
      onError: (err: any) => {
        setRunError(err?.body?.message ?? err?.message ?? "Validation failed");
      },
    },
  });

  if (projectLoading) return <LoadingState message="Loading project…" />;
  if (!project) return <ErrorState title="Project not found" />;

  const projectWithStages: ProjectWithStages = { ...project, stages: stages ?? [] };

  const defects = validationResult ? parseDefects(validationResult) : [];
  const fatalCount = defects.filter((d) => d.severity === "fatal").length;
  const errorCount = defects.filter((d) => d.severity === "error").length;
  const warningCount = defects.filter((d) => d.severity === "warning").length;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ProjectHeader project={projectWithStages} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-5">
          {/* Controls */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Validation Audit
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Runs 26+ compiler-style checks across all stage outputs.
              </p>
            </div>
            <Button
              size="sm"
              className="gap-1.5 text-xs h-8"
              onClick={() => validate({ id: projectId })}
              disabled={isPending}
            >
              {isPending ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Validating…
                </>
              ) : (
                <>
                  <ShieldCheck className="w-3.5 h-3.5" />
                  {validationResult ? "Re-run Validation" : "Run Validation"}
                </>
              )}
            </Button>
          </div>

          {runError && (
            <div className="border border-destructive/20 bg-destructive/5 rounded-sm p-3">
              <p className="text-xs text-destructive font-mono">{runError}</p>
            </div>
          )}

          {!validationResult && !isPending && (
            <div className="flex flex-col items-center gap-4 py-16 border rounded-sm bg-muted/10 text-center">
              <ShieldCheck className="w-8 h-8 text-muted-foreground/30" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">No validation run yet</p>
                <p className="text-xs text-muted-foreground">
                  Run the validation audit to check all stage outputs for completeness and coherence.
                </p>
              </div>
            </div>
          )}

          {isPending && (
            <LoadingState message="Running validation checks…" />
          )}

          {validationResult && !isPending && (
            <>
              <ValidationSummary
                verdict={validationResult.verdict ?? (validationResult.passed ? "pass" : "fail")}
                defectCount={validationResult.defect_count ?? validationResult.issueCount ?? defects.length}
                fatalCount={fatalCount}
                errorCount={errorCount}
                warningCount={warningCount}
                blockedHandoff={validationResult.blocked_handoff ?? false}
                summary={validationResult.summary}
              />

              <div className="space-y-2">
                <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">
                  Defects ({defects.length})
                </div>
                <DefectList defects={defects} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
