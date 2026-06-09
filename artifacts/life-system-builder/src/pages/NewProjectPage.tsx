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

const TUTORIAL_EXAMPLES = [
  "Build a SaaS landing page with Next.js and Tailwind",
  "Create a Discord bot with Python",
  "Build a CRUD app with Supabase",
  "Walk me through deploying a FastAPI app",
  "Build a Chrome extension for tab management",
  "Show me how to make an AI chat app with streaming responses",
];

export default function NewProjectPage() {
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [tutorialPrompt, setTutorialPrompt] = useState("");
  const [skillLevel, setSkillLevel] = useState("beginner");
  const [tutorialType, setTutorialType] = useState("hands-on build");
  const [stack, setStack] = useState("");
  const [platform, setPlatform] = useState("");
  const [desiredDepth, setDesiredDepth] = useState("detailed");
  const [includeCode, setIncludeCode] = useState(true);
  const [outputStyle, setOutputStyle] = useState("project-based");
  const [constraints, setConstraints] = useState("");
  const [context, setContext] = useState("");
  const [errors, setErrors] = useState<{ tutorialPrompt?: string }>({});

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
    if (!tutorialPrompt.trim()) errs.tutorialPrompt = "Tutorial request is required.";
    return errs;
  }

  function buildContext() {
    const details = [
      stack.trim() && `Language / framework / stack: ${stack.trim()}`,
      platform.trim() && `Platform / environment: ${platform.trim()}`,
      `Include code snippets: ${includeCode ? "yes" : "no"}`,
      constraints.trim() && `Constraints: ${constraints.trim()}`,
      context.trim() && `Additional context: ${context.trim()}`,
    ].filter(Boolean);
    return details.join("\n");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setErrors({});
    const fallbackTitle = tutorialPrompt.trim().slice(0, 90);
    createProject({
      data: {
        title: title.trim() || fallbackTitle,
        lifeEvent: tutorialPrompt.trim(),
        audience: skillLevel,
        tone: outputStyle,
        context: buildContext() || undefined,
        formattingProfile: tutorialType,
        artifactDensity: `${desiredDepth}${includeCode ? " + code snippets" : " + no code snippets"}`,
      },
    });
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-8 py-5 border-b bg-card flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <Link href="/projects">
            <span className="hover:text-foreground transition-colors cursor-pointer">Tutorials</span>
          </Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-foreground">New Tutorial</span>
        </div>
        <h1 className="text-base font-semibold text-foreground">Create a New Tutorial</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Describe what you want to learn or build, then tune the walkthrough for your stack and skill level.
        </p>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-8">
        <form onSubmit={handleSubmit} className="max-w-2xl space-y-6">
          {/* Title */}
          <div className="space-y-1.5">
            <Label htmlFor="title" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Tutorial Title <span className="font-normal normal-case">(optional)</span>
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Streaming AI Chat App Walkthrough"
              className="text-sm"
            />
          </div>

          {/* Tutorial Prompt */}
          <div className="space-y-1.5">
            <Label htmlFor="tutorialPrompt" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              What tutorial do you want? *
            </Label>
            <Textarea
              id="tutorialPrompt"
              value={tutorialPrompt}
              onChange={(e) => { setTutorialPrompt(e.target.value); setErrors((p) => ({ ...p, tutorialPrompt: undefined })); }}
              placeholder="Describe the project, coding workflow, bug, architecture, or deployment flow you want explained."
              rows={4}
              className={`text-sm resize-none ${errors.tutorialPrompt ? "border-destructive" : ""}`}
            />
            {errors.tutorialPrompt && <p className="text-xs text-destructive">{errors.tutorialPrompt}</p>}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {TUTORIAL_EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => { setTutorialPrompt(ex); setErrors((p) => ({ ...p, tutorialPrompt: undefined })); }}
                  className="text-[10px] px-2 py-1 rounded-sm border bg-muted hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>

          {/* Structured tutorial controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="skillLevel" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Skill Level
              </Label>
              <select id="skillLevel" value={skillLevel} onChange={(e) => setSkillLevel(e.target.value)} className="h-9 w-full rounded-sm border bg-background px-3 text-sm">
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tutorialType" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Tutorial Type
              </Label>
              <select id="tutorialType" value={tutorialType} onChange={(e) => setTutorialType(e.target.value)} className="h-9 w-full rounded-sm border bg-background px-3 text-sm">
                <option value="overview">Overview</option>
                <option value="hands-on build">Hands-on build</option>
                <option value="debugging walkthrough">Debugging walkthrough</option>
                <option value="architecture walkthrough">Architecture walkthrough</option>
                <option value="deployment guide">Deployment guide</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="stack" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Language / Framework / Stack
              </Label>
              <Input id="stack" value={stack} onChange={(e) => setStack(e.target.value)} placeholder="e.g. React, FastAPI, Supabase" className="text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="platform" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Platform / Environment
              </Label>
              <Input id="platform" value={platform} onChange={(e) => setPlatform(e.target.value)} placeholder="e.g. Vercel, Docker, macOS, GitHub Actions" className="text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="desiredDepth" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Desired Depth
              </Label>
              <select id="desiredDepth" value={desiredDepth} onChange={(e) => setDesiredDepth(e.target.value)} className="h-9 w-full rounded-sm border bg-background px-3 text-sm">
                <option value="concise">Concise</option>
                <option value="detailed">Detailed</option>
                <option value="deep-dive">Deep dive</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="outputStyle" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Output Style
              </Label>
              <select id="outputStyle" value={outputStyle} onChange={(e) => setOutputStyle(e.target.value)} className="h-9 w-full rounded-sm border bg-background px-3 text-sm">
                <option value="concise">Concise</option>
                <option value="detailed">Detailed</option>
                <option value="checklist-driven">Checklist-driven</option>
                <option value="project-based">Project-based</option>
              </select>
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={includeCode}
              onChange={(e) => setIncludeCode(e.target.checked)}
              className="h-4 w-4 rounded border"
            />
            Include code snippets and implementation examples where useful
          </label>

          {/* Context */}
          <div className="space-y-1.5">
            <Label htmlFor="context" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Constraints and extra context <span className="font-normal normal-case">(optional)</span>
            </Label>
            <Textarea
              id="constraints"
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              placeholder="Time budget, preferred tools, things to avoid, existing codebase assumptions, deployment limits…"
              rows={3}
              className="text-sm resize-none"
            />
            <Textarea
              id="context"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Add any background the tutorial should account for."
              rows={3}
              className="text-sm resize-none"
            />
            <p className="text-[10px] text-muted-foreground">
              More context produces a more specific tutorial plan, setup path, checkpoints, and debugging guidance.
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
              {isPending ? "Creating…" : "Create Tutorial"}
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
