import { AlertTriangle, XCircle, Info, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export interface Defect {
  code: string;
  severity: "fatal" | "error" | "warning" | string;
  title: string;
  message: string;
  stage: string;
  field_path?: string;
  evidence?: string;
  required_fix?: string;
}

const SEVERITY_CONFIG = {
  fatal: {
    icon: XCircle,
    label: "Fatal",
    headerClass: "bg-red-100 border-red-300 text-red-800",
    itemClass: "border-red-100",
    codeClass: "text-red-600",
  },
  error: {
    icon: XCircle,
    label: "Error",
    headerClass: "bg-red-50 border-red-200 text-red-700",
    itemClass: "border-red-50",
    codeClass: "text-red-500",
  },
  warning: {
    icon: AlertTriangle,
    label: "Warning",
    headerClass: "bg-amber-50 border-amber-200 text-amber-700",
    itemClass: "border-amber-50",
    codeClass: "text-amber-600",
  },
  info: {
    icon: Info,
    label: "Info",
    headerClass: "bg-blue-50 border-blue-200 text-blue-700",
    itemClass: "border-blue-50",
    codeClass: "text-blue-500",
  },
};

function DefectItem({ defect }: { defect: Defect }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = SEVERITY_CONFIG[defect.severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info;
  const Icon = cfg.icon;
  const hasDetail = defect.evidence || defect.required_fix || defect.field_path;

  return (
    <div className={cn("border rounded-sm overflow-hidden", cfg.itemClass)}>
      <div
        className={cn(
          "flex items-start gap-3 p-3",
          hasDetail && "cursor-pointer hover:bg-muted/30"
        )}
        onClick={hasDetail ? () => setExpanded(!expanded) : undefined}
      >
        <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={cn("text-[10px] font-mono font-bold uppercase", cfg.codeClass)}>
              {defect.code}
            </span>
            <span className="text-xs text-muted-foreground font-mono">
              {defect.stage}
            </span>
            {defect.field_path && (
              <span className="text-[10px] text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded-sm">
                {defect.field_path}
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-foreground mt-0.5">{defect.title}</p>
          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{defect.message}</p>
        </div>
        {hasDetail && (
          <span className="text-muted-foreground flex-shrink-0 mt-0.5">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </span>
        )}
      </div>

      {expanded && hasDetail && (
        <div className="border-t border-border/50 px-4 py-3 space-y-2 bg-muted/20">
          {defect.evidence && (
            <div>
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground mb-1">Evidence</div>
              <p className="text-xs font-mono text-foreground bg-muted/50 px-2 py-1.5 rounded-sm">{defect.evidence}</p>
            </div>
          )}
          {defect.required_fix && (
            <div>
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground mb-1">Required Fix</div>
              <p className="text-xs text-foreground leading-relaxed">{defect.required_fix}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DefectGroup({
  severity,
  defects,
}: {
  severity: string;
  defects: Defect[];
}) {
  const cfg = SEVERITY_CONFIG[severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info;

  return (
    <div className="space-y-1.5">
      <div className={cn("flex items-center gap-2 px-3 py-1.5 rounded-sm border text-xs font-semibold", cfg.headerClass)}>
        <span className="uppercase tracking-wider">{cfg.label}</span>
        <span className="font-mono bg-white/40 rounded-sm px-1.5">{defects.length}</span>
      </div>
      <div className="space-y-1.5 pl-1">
        {defects.map((d, i) => (
          <DefectItem key={`${d.code}-${i}`} defect={d} />
        ))}
      </div>
    </div>
  );
}

interface DefectListProps {
  defects: Defect[];
}

const SEVERITY_ORDER = ["fatal", "error", "warning", "info"];

export function DefectList({ defects }: DefectListProps) {
  const grouped = SEVERITY_ORDER.reduce<Record<string, Defect[]>>((acc, sev) => {
    const items = defects.filter((d) => d.severity === sev);
    if (items.length > 0) acc[sev] = items;
    return acc;
  }, {});

  if (defects.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
          <span className="text-green-600 text-lg">✓</span>
        </div>
        <p className="text-sm font-medium text-green-700">No defects found</p>
        <p className="text-xs text-muted-foreground">All validation checks passed.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([sev, items]) => (
        <DefectGroup key={sev} severity={sev} defects={items} />
      ))}
    </div>
  );
}
