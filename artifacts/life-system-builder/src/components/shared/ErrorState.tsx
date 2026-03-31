import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-4 py-16", className)}>
      <AlertTriangle className="w-8 h-8 text-destructive/60" />
      <div className="text-center space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {message && (
          <p className="text-xs text-muted-foreground max-w-md font-mono">{message}</p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Retry
        </Button>
      )}
    </div>
  );
}
