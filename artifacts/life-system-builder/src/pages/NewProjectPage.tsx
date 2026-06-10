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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TUTORIAL_EXAMPLES = [
  "Build a SaaS landing page with Next.js and Tailwind",
  "Create a Discord bot with Python",
  "Build a CRUD app with Supabase",
  "Walk me through deploying a FastAPI app",
  "Build a Chrome extension for tab management",
  "Show me how to make an AI chat app with streaming responses",
];

const SKILL_LEVELS = ["beginner", "intermediate", "advanced"] as const;
const TUTORIAL_TYPES = [
  "overview",
  "hands-on build",
  "debugging walkthrough",
  "architecture walkthrough",
  "deployment guide",
] as const;
const OUTPUT_STYLES = ["concise", "detailed", "checklist-driven", "project-based"] as const;
const DEPTH_OPTIONS = ["quick overview", "standard", "comprehensive"] as const;

export default function NewProjectPage() {
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [tutorialPrompt, setTutorialPrompt] = useState("");
  const [skillLevel, setSkillLevel] = useState<string>("beginner");
  const [tutorialType, setTutorialType] = useState<string>("hands-on build");
  const [stack, setStack] = useState("");
  const [platform, setPlatform] = useState("");
  const [depth, setDepth] = useState<string>("standard");
  const [includeCodeSnippets, setIncludeCodeSnippets] = useState(true);
  const [outputStyle, setOutputStyle] = useState<string>("project-based");
  const [constraints, setConstraints] = useState("");
  const [errors, setErrors] = useState<{ title?: string; tutorialPrompt?: string }>({});

  const { mutate: createProject, isPending, error: apiError } = useCreateProject({
    mutation: {
      onSuccess: (project) => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() });
        navigate(`/projects/${project.id}`);
      },
    },
  });

  function buildContext(): string {
    const parts: string[] = [];
    if (stack.trim()) parts.push(`Stack / language / framework: ${stack.trim()}`);
    if (platform.trim()) parts.push(`Platform / environment: ${platform.trim()}`);
    parts.push(`Include code snippets: ${includeCodeSnippets ? "yes" : "no"}`);
    if (constraints.trim()) parts.push(`Constraints: ${constraints.trim()}`);
    return parts.join("\n");
  }

  function validate() {
    const errs: typeof errors = {};
    if (!title.trim()) errs.title = "Title is required.";
    if (!tutorialPrompt.trim()) errs.tutorialPrompt = "Tutorial request is required.";
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
    createProject({
      data: {
        title: title.trim(),
        lifeEvent: tutorialPrompt.trim(),
        audience: skillLevel,
        tone: outputStyle,
        formattingProfile: tutorialType,
        artifactDensity: depth,
        context: buildContext() || undefined,
      },
    });
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-8 py-5 border-b bg-card flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <Link href="/projects">
            <span className="hover:text-foreground transition-colors cursor-pointer">Tutorials</span>
          </Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-foreground">New Tutorial</span>
        </div>
        <h1 className="text-base font-semibold text-foreground">Create a Tutorial</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Describe what you want to learn or build — get a structured walkthrough with steps, code, and checkpoints.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        <form onSubmit={handleSubmit} className="max-w-xl space-y-6">
          <div className="space-y-1.5">
            <Label htmlFor="title" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Tutorial Title *
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => { setTitle(e.target.value); setErrors((p) => ({ ...p, title: undefined })); }}
              placeholder="e.g. Next.js SaaS Landing Page — Beginner Walkthrough"
              className={`text-sm ${errors.title ? "border-destructive" : ""}`}
            />
            {errors.title && <p className="text-xs text-destructive">{errors.title}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tutorialPrompt" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              What do you want a tutorial on? *
            </Label>
            <Textarea
              id="tutorialPrompt"
              value={tutorialPrompt}
              onChange={(e) => { setTutorialPrompt(e.target.value); setErrors((p) => ({ ...p, tutorialPrompt: undefined })); }}
              placeholder="Describe the project, skill, or workflow you want to learn…"
              rows={3}
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

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Skill Level
              </Label>
              <Select value={skillLevel} onValueChange={setSkillLevel}>
                <SelectTrigger className="text-sm h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SKILL_LEVELS.map((level) => (
                    <SelectItem key={level} value={level} className="text-sm capitalize">
                      {level}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Tutorial Type
              </Label>
              <Select value={tutorialType} onValueChange={setTutorialType}>
                <SelectTrigger className="text-sm h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TUTORIAL_TYPES.map((type) => (
                    <SelectItem key={type} value={type} className="text-sm capitalize">
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="stack" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Language / Framework / Stack
              </Label>
              <Input
                id="stack"
                value={stack}
                onChange={(e) => setStack(e.target.value)}
                placeholder="e.g. Next.js 14, TypeScript, Tailwind"
                className="text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="platform" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Platform / Environment
              </Label>
              <Input
                id="platform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                placeholder="e.g. Vercel, local dev, Docker"
                className="text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Tutorial Depth
              </Label>
              <Select value={depth} onValueChange={setDepth}>
                <SelectTrigger className="text-sm h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DEPTH_OPTIONS.map((d) => (
                    <SelectItem key={d} value={d} className="text-sm capitalize">
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Output Style
              </Label>
              <Select value={outputStyle} onValueChange={setOutputStyle}>
                <SelectTrigger className="text-sm h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OUTPUT_STYLES.map((style) => (
                    <SelectItem key={style} value={style} className="text-sm capitalize">
                      {style}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Include Code Snippets
            </Label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setIncludeCodeSnippets(true)}
                className={`text-xs px-3 py-1.5 rounded-sm border transition-colors cursor-pointer ${
                  includeCodeSnippets
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-muted text-muted-foreground hover:bg-secondary"
                }`}
              >
                Yes
              </button>
              <button
                type="button"
                onClick={() => setIncludeCodeSnippets(false)}
                className={`text-xs px-3 py-1.5 rounded-sm border transition-colors cursor-pointer ${
                  !includeCodeSnippets
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-muted text-muted-foreground hover:bg-secondary"
                }`}
              >
                No
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="constraints" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Constraints <span className="font-normal normal-case">(optional)</span>
            </Label>
            <Textarea
              id="constraints"
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              placeholder="Time budget, preferred tools, things to avoid, specific requirements…"
              rows={3}
              className="text-sm resize-none"
            />
            <p className="text-[10px] text-muted-foreground">
              More detail produces tutorials better matched to your stack, skill level, and goals.
            </p>
          </div>

          {apiError && (
            <div className="border border-destructive/30 bg-destructive/5 rounded-sm px-3 py-2.5">
              <p className="text-xs text-destructive font-mono">
                {(apiError as any)?.body?.message ?? (apiError as any)?.message ?? "Failed to create tutorial."}
              </p>
            </div>
          )}

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
