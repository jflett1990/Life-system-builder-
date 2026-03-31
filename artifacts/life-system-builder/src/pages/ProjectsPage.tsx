import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { getListProjectsQueryOptions } from "@workspace/api-client-react";
import { Plus, Layers, Clock, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { Project } from "@workspace/api-client-react";

function ProjectCard({ project }: { project: Project }) {
  const createdAt = new Date(project.createdAt).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <Link href={`/projects/${project.id}`}>
      <div className="border rounded-sm bg-card hover:border-foreground/20 hover:shadow-sm transition-all cursor-pointer p-5 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-foreground truncate">{project.title}</h3>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{project.lifeEvent}</p>
          </div>
          <StatusBadge status={project.status} size="xs" />
        </div>

        {project.context && (
          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
            {project.context}
          </p>
        )}

        <div className="flex items-center gap-3 pt-1 border-t border-border/50">
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Clock className="w-3 h-3" />
            {createdAt}
          </div>
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className="font-mono">ID #{project.id}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function ProjectsPage() {
  const { data: projects, isLoading, error, refetch } = useQuery(getListProjectsQueryOptions());

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-5 border-b bg-card flex-shrink-0">
        <div>
          <h1 className="text-base font-semibold text-foreground">Projects</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {projects ? `${projects.length} project${projects.length !== 1 ? "s" : ""}` : "Life event operational systems"}
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
            message={(error as any)?.body?.message ?? (error as any)?.message}
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
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 max-w-5xl">
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
