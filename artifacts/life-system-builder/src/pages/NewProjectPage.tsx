import { useMemo, useState } from "react";
import { useLocation, Link } from "wouter";
import { useCreateProject } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { getListProjectsQueryKey } from "@workspace/api-client-react";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

const TUTORIAL_PROMPT_EXAMPLES = [
  "Build a SaaS landing page with Next.js and Tailwind",
  "Create a Discord bot with Python",
  "Build a CRUD app with Supabase",
  "Walk me through deploying a FastAPI app",
  "Build a Chrome extension for tab management",
  "Show me how to make an AI chat app with streaming responses",
];

const SKILL_LEVELS = ["Beginner", "Intermediate", "Advanced"] as const;
const TUTORIAL_TYPES = [
  "Overview",
  "Hands-on build",
  "Debugging walkthrough",
  "Architecture walkthrough",
  "Deployment guide",
] as const;
const DEPTH_OPTIONS = ["Short (30-45 min)", "Medium (60-90 min)", "Deep dive (2+ hrs)"] as const;
const OUTPUT_STYLES = ["Concise", "Detailed", "Checklist-driven", "Project-based"] as const;

export default function NewProjectPage() {
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [tutorialRequest, setTutorialRequest] = useState("");
  const [skillLevel, setSkillLevel] = useState<(typeof SKILL_LEVELS)[number]>("Intermediate");
  const [tutorialType, setTutorialType] = useState<(typeof TUTORIAL_TYPES)[number]>("Hands-on build");
  const [stack, setStack] = useState("");
  const [platform, setPlatform] = useState("");
  const [depth, setDepth] = useState<(typeof DEPTH_OPTIONS)[number]>("Medium (60-90 min)");
  const [includeCodeSnippets, setIncludeCodeSnippets] = useState(true);
  const [outputStyle, setOutputStyle] = useState<(typeof OUTPUT_STYLES)[number]>("Project-based");
  const [timeBudget, setTimeBudget] = useState("");
  const [preferredTools, setPreferredTools] = useState("");
  const [avoidTopics, setAvoidTopics] = useState("");
  const [additionalContext, setAdditionalContext] = useState("");
  const [errors, setErrors] = useState<{ title?: string; tutorialRequest?: string }>({});

  const { mutate: createProject, isPending, error: apiError } = useCreateProject({
    mutation: {
      onSuccess: (project) => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() });
        navigate(`/projects/${project.id}`);
      },
    },
  });

  const derivedTitle = useMemo(() => {
    if (!tutorialRequest.trim()) return "";
    return tutorialRequest.length > 70
      ? `${tutorialRequest.slice(0, 67).trim()}...`
      : tutorialRequest;
  }, [tutorialRequest]);

  function validate() {
    const errs: typeof errors = {};
    if (!title.trim()) errs.title = "Tutorial project title is required.";
    if (!tutorialRequest.trim()) errs.tutorialRequest = "Tutorial request is required.";
    return errs;
  }

  function buildContextBlock() {
    const lines = [
      `Tutorial type: ${tutorialType}`,
      `Skill level: ${skillLevel}`,
      `Stack / framework: ${stack.trim() || "Not specified"}`,
      `Platform / environment: ${platform.trim() || "Not specified"}`,
      `Desired depth: ${depth}`,
      `Include code snippets: ${includeCodeSnippets ? "Yes" : "No"}`,
      `Output style: ${outputStyle}`,
      `Time budget: ${timeBudget.trim() || "Not specified"}`,
      `Preferred tools: ${preferredTools.trim() || "Not specified"}`,
      `Avoid: ${avoidTopics.trim() || "None"}`,
      `Additional context: ${additionalContext.trim() || "None"}`,
    ];
    return lines.join("\n");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setErrors({});

    createProject({
      data: {
        title: title.trim(),
        lifeEvent: tutorialRequest.trim(),
        audience: skillLevel,
        tone: outputStyle,
        formattingProfile: tutorialType,
        artifactDensity: depth,
        context: buildContextBlock(),
      },
    });
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-8 py-5 border-b bg-card flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <Link href="/projects">
            <span className="hover:text-foreground transition-colors cursor-pointer">Tutorial Projects</span>
          </Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-foreground">New Tutorial</span>
        </div>
        <h1 className="text-base font-semibold text-foreground">Create a Tutorial Builder Project</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Describe what to build and set delivery preferences for a coding-first walkthrough.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        <form onSubmit={handleSubmit} className="max-w-3xl space-y-6">
          <div className="space-y-1.5">
            <Label htmlFor="title" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Tutorial Project Title *
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                setErrors((p) => ({ ...p, title: undefined }));
              }}
              placeholder="e.g. FastAPI Deployment Walkthrough for Beginners"
              className={`text-sm ${errors.title ? "border-destructive" : ""}`}
            />
            {!title && derivedTitle && (
              <button
                type="button"
                onClick={() => setTitle(derivedTitle)}
                className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              >
                Use suggestion: {derivedTitle}
              </button>
            )}
            {errors.title && <p className="text-xs text-destructive">{errors.title}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tutorialRequest" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              What tutorial do you want? *
            </Label>
            <Textarea
              id="tutorialRequest"
              value={tutorialRequest}
              onChange={(e) => {
                setTutorialRequest(e.target.value);
                setErrors((p) => ({ ...p, tutorialRequest: undefined }));
              }}
              placeholder="Describe what you want to build or learn, including expected output and constraints."
              rows={3}
              className={`text-sm resize-none ${errors.tutorialRequest ? "border-destructive" : ""}`}
            />
            {errors.tutorialRequest && <p className="text-xs text-destructive">{errors.tutorialRequest}</p>}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {TUTORIAL_PROMPT_EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => {
                    setTutorialRequest(ex);
                    if (!title.trim()) setTitle(ex);
                    setErrors((p) => ({ ...p, tutorialRequest: undefined }));
                  }}
                  className="text-[10px] px-2 py-1 rounded-sm border bg-muted hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="skillLevel" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Skill level
              </Label>
              <select
                id="skillLevel"
                value={skillLevel}
                onChange={(e) => setSkillLevel(e.target.value as (typeof SKILL_LEVELS)[number])}
                className="w-full h-9 rounded-md border bg-background px-3 text-sm"
              >
                {SKILL_LEVELS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="tutorialType" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Tutorial type
              </Label>
              <select
                id="tutorialType"
                value={tutorialType}
                onChange={(e) => setTutorialType(e.target.value as (typeof TUTORIAL_TYPES)[number])}
                className="w-full h-9 rounded-md border bg-background px-3 text-sm"
              >
                {TUTORIAL_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="stack" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Language / framework / stack
              </Label>
              <Input
                id="stack"
                value={stack}
                onChange={(e) => setStack(e.target.value)}
                placeholder="e.g. Next.js 15 + Tailwind + Prisma"
                className="text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="platform" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Platform / environment
              </Label>
              <Input
                id="platform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                placeholder="e.g. Vercel + Postgres + GitHub Actions"
                className="text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="depth" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Tutorial depth / length
              </Label>
              <select
                id="depth"
                value={depth}
                onChange={(e) => setDepth(e.target.value as (typeof DEPTH_OPTIONS)[number])}
                className="w-full h-9 rounded-md border bg-background px-3 text-sm"
              >
                {DEPTH_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="outputStyle" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Output style
              </Label>
              <select
                id="outputStyle"
                value={outputStyle}
                onChange={(e) => setOutputStyle(e.target.value as (typeof OUTPUT_STYLES)[number])}
                className="w-full h-9 rounded-md border bg-background px-3 text-sm"
              >
                {OUTPUT_STYLES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="timeBudget" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Time budget
              </Label>
              <Input
                id="timeBudget"
                value={timeBudget}
                onChange={(e) => setTimeBudget(e.target.value)}
                placeholder="e.g. 90 minutes total"
                className="text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="preferredTools" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Preferred tools
              </Label>
              <Input
                id="preferredTools"
                value={preferredTools}
                onChange={(e) => setPreferredTools(e.target.value)}
                placeholder="e.g. pnpm, VS Code, Supabase CLI"
                className="text-sm"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="avoidTopics" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Things to avoid
            </Label>
            <Input
              id="avoidTopics"
              value={avoidTopics}
              onChange={(e) => setAvoidTopics(e.target.value)}
              placeholder="e.g. Docker, paid services, OAuth complexity"
              className="text-sm"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="additionalContext" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Additional constraints or context
            </Label>
            <Textarea
              id="additionalContext"
              value={additionalContext}
              onChange={(e) => setAdditionalContext(e.target.value)}
              placeholder="Share constraints, prerequisites, or expected final deliverable format."
              rows={4}
              className="text-sm resize-none"
            />
          </div>

          <label className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={includeCodeSnippets}
              onChange={(e) => setIncludeCodeSnippets(e.target.checked)}
              className="rounded border"
            />
            Include code snippets and implementation examples
          </label>

          {apiError && (
            <div className="border border-destructive/30 bg-destructive/5 rounded-sm px-3 py-2.5">
              <p className="text-xs text-destructive font-mono">
                {(apiError as any)?.body?.message ?? (apiError as any)?.message ?? "Failed to create tutorial project."}
              </p>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <Button type="submit" disabled={isPending} className="gap-1.5">
              {isPending ? "Creating…" : "Create Tutorial Project"}
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
