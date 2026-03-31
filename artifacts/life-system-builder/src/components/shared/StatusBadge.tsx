import { cn } from "@/lib/utils";

type Status = "pending" | "running" | "complete" | "failed" | "pass" | "fail" | "conditional_pass" | "skipped" | string;

const STATUS_CONFIG: Record<string, { label: string; className: string; dot?: string }> = {
  pending:          { label: "Pending",    className: "bg-muted text-muted-foreground",       dot: "bg-muted-foreground/50" },
  running:          { label: "Running",    className: "bg-blue-50 text-blue-700 border-blue-200",   dot: "bg-blue-500 animate-pulse" },
  complete:         { label: "Complete",   className: "bg-green-50 text-green-700 border-green-200", dot: "bg-green-500" },
  failed:           { label: "Failed",     className: "bg-red-50 text-red-700 border-red-200",      dot: "bg-red-500" },
  pass:             { label: "Pass",       className: "bg-green-50 text-green-700 border-green-200", dot: "bg-green-500" },
  fail:             { label: "Fail",       className: "bg-red-50 text-red-700 border-red-200",      dot: "bg-red-500" },
  conditional_pass: { label: "Cond. Pass", className: "bg-amber-50 text-amber-700 border-amber-200", dot: "bg-amber-500" },
  skipped:          { label: "Skipped",   className: "bg-muted text-muted-foreground",       dot: "bg-muted-foreground/30" },
  fatal:            { label: "Fatal",      className: "bg-red-100 text-red-800 border-red-300",     dot: "bg-red-700" },
  error:            { label: "Error",      className: "bg-red-50 text-red-700 border-red-200",      dot: "bg-red-500" },
  warning:          { label: "Warning",    className: "bg-amber-50 text-amber-700 border-amber-200", dot: "bg-amber-400" },
  info:             { label: "Info",       className: "bg-blue-50 text-blue-700 border-blue-200",   dot: "bg-blue-400" },
};

interface StatusBadgeProps {
  status: Status;
  className?: string;
  showDot?: boolean;
  size?: "xs" | "sm" | "md";
}

export function StatusBadge({ status, className, showDot = true, size = "sm" }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    className: "bg-muted text-muted-foreground",
    dot: "bg-muted-foreground/50",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono tracking-wide border rounded-sm",
        size === "xs" && "text-[9px] px-1.5 py-0.5 uppercase",
        size === "sm" && "text-[10px] px-2 py-1 uppercase",
        size === "md" && "text-xs px-2.5 py-1 uppercase",
        config.className,
        className
      )}
    >
      {showDot && (
        <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", config.dot)} />
      )}
      {config.label}
    </span>
  );
}
