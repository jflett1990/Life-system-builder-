import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "wouter";
import { getListProjectsQueryOptions, getListProjectStagesQueryOptions } from "@workspace/api-client-react";
import { Layers, Plus, FolderOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Project } from "@workspace/api-client-react";

function ProjectItem({ project }: { project: Project }) {
  const [location] = useLocation();
  const href = `/projects/${project.id}`;
  const isActive = location.startsWith(href);

  const { data: stages } = useQuery({
    ...getListProjectStagesQueryOptions(project.id),
    staleTime: 30_000,
  });

  const completedCount = stages?.filter((s) => s.status === "complete").length ?? 0;
  const totalStages = 5;

  return (
    <Link href={href}>
      <div
        className={cn(
          "group flex items-start gap-2.5 px-3 py-2.5 cursor-pointer rounded-sm transition-colors",
          isActive
            ? "bg-sidebar-accent text-sidebar-accent-foreground"
            : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
        )}
      >
        <FolderOpen className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 opacity-60" />
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium truncate leading-tight">
            {project.title}
          </div>
          <div className="text-[10px] text-sidebar-foreground/40 mt-0.5 truncate">
            {project.lifeEvent}
          </div>
        </div>
        <div
          className="flex-shrink-0 text-[9px] font-mono text-sidebar-foreground/30 mt-0.5"
          title={`${completedCount} of ${totalStages} stages complete`}
        >
          {completedCount}/{totalStages}
        </div>
      </div>
    </Link>
  );
}

export default function AppSidebar() {
  const [location] = useLocation();
  const { data: projects, isLoading } = useQuery(getListProjectsQueryOptions());

  return (
    <aside className="w-[240px] flex-shrink-0 flex flex-col h-full bg-sidebar border-r border-sidebar-border">
      {/* Brand */}
      <div className="px-4 pt-5 pb-4 border-b border-sidebar-border">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 bg-sidebar-primary/20 border border-sidebar-primary/30 flex items-center justify-center rounded-sm">
            <Layers className="w-3.5 h-3.5 text-sidebar-primary" />
          </div>
          <div>
            <div className="text-[11px] font-semibold tracking-wider uppercase text-sidebar-foreground/90 leading-tight">
              Life System
            </div>
            <div className="text-[9px] tracking-widest uppercase text-sidebar-foreground/35 leading-tight">
              Builder
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <div className="flex-1 overflow-y-auto py-3 min-h-0">
        <div className="px-3 mb-3">
          <Link href="/projects">
            <div
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-sm text-xs cursor-pointer transition-colors",
                location === "/projects"
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent/60"
              )}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Dashboard</span>
            </div>
          </Link>
        </div>

        <div className="px-3 mb-1">
          <div className="text-[9px] font-semibold tracking-widest uppercase text-sidebar-foreground/25 px-3 mb-1">
            Projects
          </div>
        </div>

        <div className="px-3 space-y-0.5">
          {isLoading && (
            <div className="px-3 py-2 text-[10px] text-sidebar-foreground/30">Loading…</div>
          )}
          {!isLoading && (!projects || projects.length === 0) && (
            <div className="px-3 py-2 text-[10px] text-sidebar-foreground/30">No projects yet</div>
          )}
          {projects?.map((project) => (
            <ProjectItem key={project.id} project={project} />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-sidebar-border">
        <Link href="/projects/new">
          <div className="flex items-center gap-2 px-3 py-2.5 rounded-sm cursor-pointer border border-sidebar-primary/30 bg-sidebar-primary/10 hover:bg-sidebar-primary/20 text-sidebar-primary transition-colors">
            <Plus className="w-3.5 h-3.5" />
            <span className="text-xs font-medium">New Project</span>
          </div>
        </Link>
      </div>
    </aside>
  );
}
