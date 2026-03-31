import { useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2, Printer, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DocumentFrameProps {
  html: string;
  pageCount?: number;
  className?: string;
}

export function DocumentFrame({ html, pageCount, className }: DocumentFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const blobUrlRef = useRef<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [key, setKey] = useState(0);

  // Build a Blob URL from the HTML string.
  // Blob URLs (blob:) allow scripts to run inside a sandboxed iframe,
  // unlike data: URIs which are blocked by most CSPs when scripts are enabled.
  useEffect(() => {
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    blobUrlRef.current = url;
    setBlobUrl(url);

    return () => {
      URL.revokeObjectURL(url);
      blobUrlRef.current = null;
    };
  }, [html]);

  function handleRefresh() {
    setKey((k) => k + 1);
  }

  function handlePrint() {
    iframeRef.current?.contentWindow?.print();
  }

  if (!blobUrl) return null;

  return (
    <div className={cn("flex flex-col rounded-sm border bg-muted/30", fullscreen && "fixed inset-0 z-50 bg-background rounded-none border-none", className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/20 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Document Preview</span>
          {pageCount !== undefined && (
            <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded-sm">
              {pageCount} page{pageCount !== 1 ? "s" : ""}
            </span>
          )}
          <span className="text-[10px] text-muted-foreground/50 hidden sm:inline">· paginated by Pagedjs</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 gap-1 text-[10px] font-normal"
            onClick={handlePrint}
            title="Print / Save as PDF"
          >
            <Printer className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Print</span>
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={handleRefresh} title="Reload">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={() => setFullscreen(!fullscreen)}
            title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {fullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </Button>
        </div>
      </div>

      {/* Frame */}
      <div className={cn("flex-1 overflow-hidden", fullscreen ? "min-h-0" : "h-[700px]")}>
        <iframe
          key={key}
          ref={iframeRef}
          src={blobUrl}
          className="w-full h-full border-0 bg-white"
          sandbox="allow-same-origin allow-scripts"
          title="Document Preview"
        />
      </div>
    </div>
  );
}
