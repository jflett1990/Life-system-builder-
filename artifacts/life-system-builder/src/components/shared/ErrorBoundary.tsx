import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex flex-col items-center justify-center gap-4 py-24 px-8 text-center">
          <AlertTriangle className="w-8 h-8 text-destructive/60" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">Something went wrong</p>
            {this.state.error?.message && (
              <p className="text-xs text-muted-foreground font-mono max-w-md">
                {this.state.error.message}
              </p>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={this.handleReset}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
