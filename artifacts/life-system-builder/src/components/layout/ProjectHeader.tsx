import { Link, useLocation } from "wouter";
import { ChevronRight, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { ProjectWithStages } from "@workspace/api-client-react";

const TABS = [
  { label: "Pipeline", path: "" },
  { label: "Validation", path: "/validation" },
  { label: "Preview", path: "/preview" },
  { label: "Export", path: "/export" },
];

interface ProjectHeaderProps {
  project: ProjectWithStages;
}

export function ProjectHeader({ project }: ProjectHeaderProps) {
  const [location] = useLocation();
  const base = `/projects/${project.id}`;

  const completedStages = project.stages.filter((s) => s.status === "complete").length;
  const totalStages = 5;

  return (
    <div className="border-b bg-card flex-shrink-0">
      {/* Breadcrumb row */}
      <div className="flex items-center gap-2 px-6 pt-4 pb-3">
        <Link href="/projects">
          <span className="text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer flex items-center gap-1">
            <Layers className="w-3 h-3" />
            Projects
          </span>
        </Link>
        <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
        <span className="text-xs font-medium text-foreground truncate max-w-xs">
          {project.title}
        </span>
      </div>

      {/* Title row */}
      <div className="flex items-start justify-between gap-4 px-6 pb-3">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-foreground leading-tight">
            {project.title}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-muted-foreground">{project.lifeEvent}</span>
            <StatusBadge status={project.status} size="xs" />
            <span className="text-[10px] font-mono text-muted-foreground">
              {completedStages}/{totalStages} stages
            </span>
          </div>
        </div>
      </div>

      {/* Tab row */}
      <div className="flex items-center gap-0 px-6 -mb-px">
        {TABS.map((tab) => {
          const href = `${base}${tab.path}`;
          const isActive = tab.path === "" 
            ? location === base || location === `${base}/`
            : location.startsWith(href);
          return (
            <Link key={tab.label} href={href}>
              <div className={cn(
                "px-4 py-2 text-xs font-medium cursor-pointer border-b-2 transition-colors",
                isActive
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}>
                {tab.label}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
