import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "wouter";
import {
  getListProjectsQueryOptions,
  getListProjectsQueryKey,
  useDuplicateProject,
} from "@workspace/api-client-react";
import { Plus, Layers, Clock, Copy, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { Project } from "@workspace/api-client-react";

function ProjectCard({ project, onDuplicate }: { project: Project; onDuplicate: (id: number) => void }) {
  const [, navigate] = useLocation();

  const createdAt = new Date(project.createdAt).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="border rounded-sm bg-card hover:border-foreground/20 hover:shadow-sm transition-all p-5 flex flex-col gap-3 group">
      <div
        className="flex items-start justify-between gap-2 cursor-pointer"
        onClick={() => navigate(`/projects/${project.id}`)}
      >
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-foreground truncate">{project.title}</h3>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{project.lifeEvent}</p>
        </div>
        <StatusBadge status={project.status} size="xs" />
      </div>

      {project.context && (
        <p
          className="text-xs text-muted-foreground leading-relaxed line-clamp-2 cursor-pointer"
          onClick={() => navigate(`/projects/${project.id}`)}
        >
          {project.context}
        </p>
      )}

      <div className="flex items-center justify-between pt-1 border-t border-border/50">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Clock className="w-3 h-3" />
            {createdAt}
          </div>
          <div className="text-[10px] font-mono text-muted-foreground/50">
            #{project.id}
          </div>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDuplicate(project.id); }}
          className="opacity-0 group-hover:opacity-100 flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-all px-2 py-1 rounded-sm hover:bg-muted"
          title="Duplicate project"
        >
          <Copy className="w-3 h-3" />
          Duplicate
        </button>
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");

  const { data: projects, isLoading, error, refetch } = useQuery(getListProjectsQueryOptions());

  const { mutate: duplicate } = useDuplicateProject({
    mutation: {
      onSuccess: (newProject) => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() });
        navigate(`/projects/${newProject.id}`);
      },
    },
  });

  const filtered = projects?.filter((p) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      p.title.toLowerCase().includes(q) ||
      p.lifeEvent.toLowerCase().includes(q) ||
      (p.context ?? "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-5 border-b bg-card flex-shrink-0">
        <div>
          <h1 className="text-base font-semibold text-foreground">Projects</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {projects
              ? `${projects.length} project${projects.length !== 1 ? "s" : ""}`
              : "Life event operational systems"}
          </p>
        </div>
        <Link href="/projects/new">
          <Button size="sm" className="gap-1.5 text-xs h-8">
            <Plus className="w-3.5 h-3.5" />
            New Project
          </Button>
        </Link>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        {isLoading && <LoadingState message="Loading projects…" />}

        {error && (
          <ErrorState
            title="Could not load projects"
            message={(error as any)?.body?.detail ?? (error as any)?.message}
            onRetry={() => refetch()}
          />
        )}

        {!isLoading && !error && projects && projects.length === 0 && (
          <div className="flex flex-col items-center gap-5 py-24 text-center">
            <div className="w-12 h-12 border-2 border-border rounded-sm flex items-center justify-center">
              <Layers className="w-6 h-6 text-muted-foreground/50" />
            </div>
            <div className="space-y-1.5">
              <h3 className="text-sm font-medium text-foreground">No projects yet</h3>
              <p className="text-xs text-muted-foreground max-w-sm">
                Create a project to convert a life event into a structured operational system.
              </p>
            </div>
            <Link href="/projects/new">
              <Button size="sm" className="gap-1.5">
                <Plus className="w-3.5 h-3.5" />
                Create first project
              </Button>
            </Link>
          </div>
        )}

        {!isLoading && !error && projects && projects.length > 0 && (
          <div className="max-w-5xl space-y-5">
            {/* Search */}
            <div className="relative max-w-sm">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search projects…"
                className="pl-8 h-8 text-xs"
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {filtered && filtered.length === 0 && (
              <div className="text-center py-16">
                <p className="text-sm text-muted-foreground">
                  No projects match <span className="font-mono">"{search}"</span>
                </p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {(filtered ?? []).map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onDuplicate={(id) => duplicate({ id })}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
