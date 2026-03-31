import { useState } from "react";
import { ChevronRight, ChevronDown, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-muted"
    >
      {copied ? (
        <Check className="w-3 h-3 text-green-600" />
      ) : (
        <Copy className="w-3 h-3 text-muted-foreground" />
      )}
    </button>
  );
}

function JsonNode({
  value,
  depth = 0,
  keyName,
  isLast = true,
}: {
  value: JsonValue;
  depth?: number;
  keyName?: string;
  isLast?: boolean;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const indent = depth * 16;

  const renderKey = keyName !== undefined ? (
    <span className="text-blue-700 dark:text-blue-400">"{keyName}"</span>
  ) : null;

  if (value === null) {
    return (
      <div style={{ paddingLeft: indent }} className="flex items-center gap-1 group">
        {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
        <span className="text-muted-foreground italic">null</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
      </div>
    );
  }

  if (typeof value === "boolean") {
    return (
      <div style={{ paddingLeft: indent }} className="flex items-center gap-1 group">
        {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
        <span className="text-amber-600">{String(value)}</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div style={{ paddingLeft: indent }} className="flex items-center gap-1 group">
        {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
        <span className="text-orange-600">{value}</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
      </div>
    );
  }

  if (typeof value === "string") {
    const display = value.length > 200 ? value.slice(0, 200) + "…" : value;
    return (
      <div style={{ paddingLeft: indent }} className="flex items-start gap-1 group">
        {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
        <span className="text-green-700 dark:text-green-400 break-all">"{display}"</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
        <CopyButton value={value} />
      </div>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <div style={{ paddingLeft: indent }} className="flex items-center gap-1">
          {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
          <span className="text-muted-foreground">[]</span>
          {!isLast && <span className="text-muted-foreground">,</span>}
        </div>
      );
    }
    return (
      <div style={{ paddingLeft: indent }}>
        <div className="flex items-center gap-1 cursor-pointer select-none group" onClick={() => setExpanded(!expanded)}>
          <span className="text-muted-foreground/60 w-3">
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </span>
          {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
          <span className="text-muted-foreground">[</span>
          {!expanded && (
            <span className="text-muted-foreground/60 text-[10px]">{value.length} items</span>
          )}
          {!expanded && <span className="text-muted-foreground">]{!isLast && ","}</span>}
        </div>
        {expanded && (
          <div>
            {value.map((item, i) => (
              <JsonNode key={i} value={item as JsonValue} depth={depth + 1} isLast={i === value.length - 1} />
            ))}
            <div style={{ paddingLeft: 0 }} className="text-muted-foreground">
              ]{!isLast && ","}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return (
        <div style={{ paddingLeft: indent }} className="flex items-center gap-1">
          {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
          <span className="text-muted-foreground">{"{}"}</span>
          {!isLast && <span className="text-muted-foreground">,</span>}
        </div>
      );
    }
    return (
      <div style={{ paddingLeft: indent }}>
        <div className="flex items-center gap-1 cursor-pointer select-none" onClick={() => setExpanded(!expanded)}>
          <span className="text-muted-foreground/60 w-3">
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </span>
          {renderKey && <>{renderKey}<span className="text-muted-foreground">: </span></>}
          <span className="text-muted-foreground">{"{"}</span>
          {!expanded && (
            <span className="text-muted-foreground/60 text-[10px]">{entries.length} keys</span>
          )}
          {!expanded && <span className="text-muted-foreground">{"}"}{!isLast && ","}</span>}
        </div>
        {expanded && (
          <div>
            {entries.map(([k, v], i) => (
              <JsonNode key={k} value={v as JsonValue} depth={depth + 1} keyName={k} isLast={i === entries.length - 1} />
            ))}
            <div className="text-muted-foreground">{"}"}{!isLast && ","}</div>
          </div>
        )}
      </div>
    );
  }

  return null;
}

interface JsonViewerProps {
  data: unknown;
  className?: string;
}

export function JsonViewer({ data, className }: JsonViewerProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopyAll() {
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className={cn("relative rounded-sm border bg-card", className)}>
      <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/30">
        <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">JSON Output</span>
        <button
          onClick={handleCopyAll}
          className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
          {copied ? "Copied" : "Copy all"}
        </button>
      </div>
      <div className="p-4 overflow-auto font-mono text-[11px] leading-relaxed max-h-[600px]">
        <JsonNode value={data as JsonValue} />
      </div>
    </div>
  );
}
