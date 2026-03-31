import { CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ValidationSummaryProps {
  verdict: string;
  defectCount: number;
  fatalCount: number;
  errorCount: number;
  warningCount: number;
  blockedHandoff: boolean;
  summary?: string;
}

export function ValidationSummary({
  verdict,
  defectCount,
  fatalCount,
  errorCount,
  warningCount,
  blockedHandoff,
  summary,
}: ValidationSummaryProps) {
  const isPassed = verdict === "pass";
  const isFailed = verdict === "fail";
  const isConditional = verdict === "conditional_pass";

  const Icon = isPassed ? CheckCircle2 : isFailed ? XCircle : AlertCircle;
  const verdictLabel = isPassed ? "Validation Passed" : isFailed ? "Validation Failed" : "Conditional Pass";

  return (
    <div className={cn(
      "rounded-sm border p-4",
      isPassed && "border-green-200 bg-green-50",
      isFailed && "border-red-200 bg-red-50",
      isConditional && "border-amber-200 bg-amber-50",
    )}>
      <div className="flex items-start gap-3">
        <Icon className={cn(
          "w-5 h-5 flex-shrink-0 mt-0.5",
          isPassed && "text-green-600",
          isFailed && "text-red-600",
          isConditional && "text-amber-600",
        )} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className={cn(
              "text-sm font-semibold",
              isPassed && "text-green-800",
              isFailed && "text-red-800",
              isConditional && "text-amber-800",
            )}>
              {verdictLabel}
            </h3>
            {blockedHandoff && (
              <span className="text-[10px] font-mono px-2 py-0.5 bg-red-100 border border-red-300 text-red-700 rounded-sm uppercase tracking-wider">
                Handoff Blocked
              </span>
            )}
          </div>

          {summary && (
            <p className={cn(
              "text-xs mt-1 leading-relaxed",
              isPassed && "text-green-700",
              isFailed && "text-red-700",
              isConditional && "text-amber-700",
            )}>
              {summary}
            </p>
          )}

          {defectCount > 0 && (
            <div className="flex items-center gap-3 mt-2">
              {fatalCount > 0 && (
                <span className="text-[10px] font-mono text-red-700">
                  {fatalCount} fatal
                </span>
              )}
              {errorCount > 0 && (
                <span className="text-[10px] font-mono text-red-600">
                  {errorCount} error{errorCount !== 1 ? "s" : ""}
                </span>
              )}
              {warningCount > 0 && (
                <span className="text-[10px] font-mono text-amber-600">
                  {warningCount} warning{warningCount !== 1 ? "s" : ""}
                </span>
              )}
              <span className="text-[10px] font-mono text-muted-foreground">
                {defectCount} total defect{defectCount !== 1 ? "s" : ""}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
