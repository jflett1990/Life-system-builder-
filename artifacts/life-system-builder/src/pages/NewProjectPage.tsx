import { useState } from "react";
import { useLocation, Link } from "wouter";
import { useCreateProject } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { getListProjectsQueryKey } from "@workspace/api-client-react";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

const LIFE_EVENT_EXAMPLES = [
  "Estate administration after parent's death",
  "Caring for an aging parent with dementia",
  "Managing divorce and asset division",
  "Transitioning a family business to next generation",
  "Navigating a sudden disability or medical crisis",
  "Coordinating post-disaster recovery",
];

export default function NewProjectPage() {
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [lifeEvent, setLifeEvent] = useState("");
  const [context, setContext] = useState("");
  const [errors, setErrors] = useState<{ title?: string; lifeEvent?: string }>({});

  const { mutate: createProject, isPending, error: apiError } = useCreateProject({
    mutation: {
      onSuccess: (project) => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() });
        navigate(`/projects/${project.id}`);
      },
    },
  });

  function validate() {
    const errs: typeof errors = {};
    if (!title.trim()) errs.title = "Title is required.";
    if (!lifeEvent.trim()) errs.lifeEvent = "Life event description is required.";
    return errs;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setErrors({});
    createProject({ data: { title: title.trim(), lifeEvent: lifeEvent.trim(), context: context.trim() || undefined } });
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-8 py-5 border-b bg-card flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <Link href="/projects">
            <span className="hover:text-foreground transition-colors cursor-pointer">Projects</span>
          </Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-foreground">New Project</span>
        </div>
        <h1 className="text-base font-semibold text-foreground">Create a New Project</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Define the life event and context to generate a structured operational system.
        </p>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-8">
        <form onSubmit={handleSubmit} className="max-w-xl space-y-6">
          {/* Title */}
          <div className="space-y-1.5">
            <Label htmlFor="title" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Project Title *
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => { setTitle(e.target.value); setErrors((p) => ({ ...p, title: undefined })); }}
              placeholder="e.g. Dad's Estate Administration — Spring 2026"
              className={`text-sm ${errors.title ? "border-destructive" : ""}`}
            />
            {errors.title && <p className="text-xs text-destructive">{errors.title}</p>}
          </div>

          {/* Life Event */}
          <div className="space-y-1.5">
            <Label htmlFor="lifeEvent" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Life Event *
            </Label>
            <Input
              id="lifeEvent"
              value={lifeEvent}
              onChange={(e) => { setLifeEvent(e.target.value); setErrors((p) => ({ ...p, lifeEvent: undefined })); }}
              placeholder="Describe the life event in a phrase"
              className={`text-sm ${errors.lifeEvent ? "border-destructive" : ""}`}
            />
            {errors.lifeEvent && <p className="text-xs text-destructive">{errors.lifeEvent}</p>}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {LIFE_EVENT_EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => { setLifeEvent(ex); setErrors((p) => ({ ...p, lifeEvent: undefined })); }}
                  className="text-[10px] px-2 py-1 rounded-sm border bg-muted hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>

          {/* Context */}
          <div className="space-y-1.5">
            <Label htmlFor="context" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Context <span className="font-normal normal-case">(optional)</span>
            </Label>
            <Textarea
              id="context"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Provide any additional context: family structure, jurisdiction, key stakeholders, urgency, known complications…"
              rows={5}
              className="text-sm resize-none"
            />
            <p className="text-[10px] text-muted-foreground">
              More context produces more accurate and specific operational systems.
            </p>
          </div>

          {/* API Error */}
          {apiError && (
            <div className="border border-destructive/30 bg-destructive/5 rounded-sm px-3 py-2.5">
              <p className="text-xs text-destructive font-mono">
                {(apiError as any)?.body?.message ?? (apiError as any)?.message ?? "Failed to create project."}
              </p>
            </div>
          )}

          {/* Submit */}
          <div className="flex items-center gap-3 pt-2">
            <Button type="submit" disabled={isPending} className="gap-1.5">
              {isPending ? "Creating…" : "Create Project"}
              {!isPending && <ChevronRight className="w-3.5 h-3.5" />}
            </Button>
            <Link href="/projects">
              <Button type="button" variant="ghost" size="sm" className="gap-1">
                <ArrowLeft className="w-3.5 h-3.5" />
                Cancel
              </Button>
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
