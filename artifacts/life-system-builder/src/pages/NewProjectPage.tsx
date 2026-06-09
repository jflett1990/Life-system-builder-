import { useState } from "react";
import { useLocation, Link } from "wouter";
import { useCreateProject } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { getListProjectsQueryKey } from "@workspace/api-client-react";
import { ArrowLeft, ChevronRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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

const SKILL_LEVELS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];

const TUTORIAL_TYPES = [
  { value: "hands-on build", label: "Hands-on build" },
  { value: "overview", label: "Overview" },
  { value: "debugging walkthrough", label: "Debugging walkthrough" },
  { value: "architecture walkthrough", label: "Architecture walkthrough" },
  { value: "deployment guide", label: "Deployment guide" },
];

const DEPTHS = [
  { value: "quick", label: "Quick (~30 min)" },
  { value: "standard", label: "Standard (2–3 h)" },
  { value: "deep-dive", label: "Deep dive (weekend)" },
];

const OUTPUT_STYLES = [
  { value: "project-based", label: "Project-based" },
  { value: "concise", label: "Concise" },
  { value: "detailed", label: "Detailed" },
  { value: "checklist-driven", label: "Checklist-driven" },
];

export default function NewProjectPage() {
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [skillLevel, setSkillLevel] = useState("intermediate");
  const [tutorialType, setTutorialType] = useState("hands-on build");
  const [stack, setStack] = useState("");
  const [platform, setPlatform] = useState("");
  const [depth, setDepth] = useState("standard");
  const [outputStyle, setOutputStyle] = useState("project-based");
  const [includeCode, setIncludeCode] = useState(true);
  const [constraints, setConstraints] = useState("");
  const [context, setContext] = useState("");
  const [errors, setErrors] = useState<{ title?: string; topic?: string }>({});

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
    if (!topic.trim()) errs.topic = "Describe what you want a tutorial on.";
    return errs;
  }

  function applyExample(example: string) {
    setTopic(example);
    if (!title.trim()) setTitle(example);
    setErrors((p) => ({ ...p, topic: undefined, title: undefined }));
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
        topic: topic.trim(),
        skillLevel,
        tutorialType,
        stack: stack.trim() || undefined,
        platform: platform.trim() || undefined,
        depth,
        outputStyle,
        includeCode,
        constraints: constraints.trim() || undefined,
        context: context.trim() || undefined,
      },
    });
  }

  const labelCls = "text-xs font-semibold uppercase tracking-wider text-muted-foreground";

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
        <h1 className="text-base font-semibold text-foreground">Create a Tutorial</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Describe what you want to build or learn — get a structured, step-by-step walkthrough.
        </p>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-8">
        <form onSubmit={handleSubmit} className="max-w-2xl space-y-6">
          {/* Topic — the primary prompt */}
          <div className="space-y-1.5">
            <Label htmlFor="topic" className={labelCls}>
              What do you want a tutorial on? *
            </Label>
            <Textarea
              id="topic"
              value={topic}
              onChange={(e) => { setTopic(e.target.value); setErrors((p) => ({ ...p, topic: undefined })); }}
              placeholder="e.g. Build a SaaS landing page with Next.js and Tailwind, with a working email-capture form and deployment to Vercel"
              rows={3}
              className={`text-sm resize-none ${errors.topic ? "border-destructive" : ""}`}
            />
            {errors.topic && <p className="text-xs text-destructive">{errors.topic}</p>}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {TUTORIAL_EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => applyExample(ex)}
                  className="text-[10px] px-2 py-1 rounded-sm border bg-muted hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors cursor-pointer inline-flex items-center gap-1"
                >
                  <Sparkles className="w-2.5 h-2.5 opacity-50" />
                  {ex}
                </button>
              ))}
            </div>
          </div>

          {/* Title */}
          <div className="space-y-1.5">
            <Label htmlFor="title" className={labelCls}>
              Tutorial Title *
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => { setTitle(e.target.value); setErrors((p) => ({ ...p, title: undefined })); }}
              placeholder="e.g. Next.js Landing Page — Weekend Build"
              className={`text-sm ${errors.title ? "border-destructive" : ""}`}
            />
            {errors.title && <p className="text-xs text-destructive">{errors.title}</p>}
          </div>

          {/* Structured controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-5">
            <div className="space-y-1.5">
              <Label className={labelCls}>Skill Level</Label>
              <Select value={skillLevel} onValueChange={setSkillLevel}>
                <SelectTrigger className="text-sm w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SKILL_LEVELS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className={labelCls}>Tutorial Type</Label>
              <Select value={tutorialType} onValueChange={setTutorialType}>
                <SelectTrigger className="text-sm w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TUTORIAL_TYPES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="stack" className={labelCls}>
                Stack / Language <span className="font-normal normal-case">(optional)</span>
              </Label>
              <Input
                id="stack"
                value={stack}
                onChange={(e) => setStack(e.target.value)}
                placeholder="e.g. Next.js 14, Tailwind, Supabase"
                className="text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="platform" className={labelCls}>
                Platform / Environment <span className="font-normal normal-case">(optional)</span>
              </Label>
              <Input
                id="platform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                placeholder="e.g. macOS, Node 20, Vercel"
                className="text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label className={labelCls}>Depth</Label>
              <Select value={depth} onValueChange={setDepth}>
                <SelectTrigger className="text-sm w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {DEPTHS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className={labelCls}>Output Style</Label>
              <Select value={outputStyle} onValueChange={setOutputStyle}>
                <SelectTrigger className="text-sm w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {OUTPUT_STYLES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Include code toggle */}
          <div className="flex items-center justify-between border rounded-sm px-4 py-3 bg-muted/20">
            <div>
              <Label htmlFor="includeCode" className="text-xs font-semibold text-foreground">
                Include code snippets
              </Label>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Runnable commands and code at every implementation step.
              </p>
            </div>
            <Switch id="includeCode" checked={includeCode} onCheckedChange={setIncludeCode} />
          </div>

          {/* Constraints */}
          <div className="space-y-1.5">
            <Label htmlFor="constraints" className={labelCls}>
              Constraints <span className="font-normal normal-case">(optional)</span>
            </Label>
            <Textarea
              id="constraints"
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              placeholder="Time budget, preferred tools, things to avoid… e.g. two evenings max, no Docker, free-tier services only"
              rows={2}
              className="text-sm resize-none"
            />
          </div>

          {/* Context */}
          <div className="space-y-1.5">
            <Label htmlFor="context" className={labelCls}>
              Additional Context <span className="font-normal normal-case">(optional)</span>
            </Label>
            <Textarea
              id="context"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="What you already know, what you've tried, the project this is for…"
              rows={3}
              className="text-sm resize-none"
            />
            <p className="text-[10px] text-muted-foreground">
              More context produces a more specific, runnable tutorial.
            </p>
          </div>

          {/* API Error */}
          {apiError && (
            <div className="border border-destructive/30 bg-destructive/5 rounded-sm px-3 py-2.5">
              <p className="text-xs text-destructive font-mono">
                {(apiError as any)?.body?.message ?? (apiError as any)?.message ?? "Failed to create tutorial."}
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
