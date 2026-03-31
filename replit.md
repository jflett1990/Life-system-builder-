# Life System Builder

## Overview

Full-stack web application that converts life events (caregiving, estate administration, divorce, etc.) into structured operational control systems. Produces structured JSON per pipeline stage, validation reports, and print-ready HTML/CSS documents.

## Architecture

pnpm monorepo with:
- **Backend**: Python FastAPI + PostgreSQL (port 8080)
- **Frontend**: React + Vite (port configured via `PORT` env var)
- **API Client**: Orval-generated React Query hooks (`lib/api-client-react/`)

## Stack

- **Monorepo**: pnpm workspaces
- **Frontend**: React 19, Vite 7, Tailwind v4, shadcn/ui, TanStack Query, Wouter
- **Backend**: Python FastAPI, SQLAlchemy, Pydantic v2, Uvicorn
- **Database**: Replit PostgreSQL (env: `DATABASE_URL`)
- **AI**: OpenAI via Replit AI Integrations (`AI_INTEGRATIONS_OPENAI_BASE_URL` + `AI_INTEGRATIONS_OPENAI_API_KEY`), model `gpt-5.2`
- **API Codegen**: Orval (OpenAPI → React Query hooks + TypeScript types)
- **HTML Render**: Jinja2 templates + custom CSS design system

## Key Design Decisions

1. **snake_case → camelCase**: The FastAPI backend returns snake_case JSON. `lib/api-client-react/src/custom-fetch.ts` contains a `deepCamelKeys` transformer that converts all response keys to camelCase automatically. This means the TypeScript types (camelCase) match what the frontend receives.

2. **Stage name normalization**: Backend uses underscores (`system_architecture`), TypeScript client uses hyphens (`system-architecture`). `schemas/stage.py` has `normalize_stage_name()` to accept both formats, and `StageOutputResponse.from_orm_with_json()` converts to hyphen format for responses.

3. **Prompt contracts**: All LLM prompts are stored as JSON files in `artifacts/api-server/contracts/`. No hardcoded prompts in routes. The `ContractRegistry` loads them at startup.

4. **Strict separation**: `prompt_assembler.py` composes prompts from contracts + project data. `pipeline_orchestrator.py` sequences stages. Routes are thin adapters.

## Structure

```text
workspace/
├── artifacts/
│   ├── api-server/           # Python FastAPI backend (port 8080)
│   │   ├── main.py           # FastAPI app, router registration
│   │   ├── api/routes/       # Route handlers (projects, pipeline, render, export)
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── services/         # Business logic (ProjectService, PipelineService, etc.)
│   │   ├── core/             # ContractLoader, ContractRegistry, PromptAssembler, PipelineOrchestrator
│   │   ├── contracts/        # JSON prompt contracts (7 total)
│   │   ├── render/           # Jinja2 HTML/CSS rendering system
│   │   │   ├── styles/       # tokens.css, base.css, print.css
│   │   │   ├── templates/    # 8 page archetypes + 9 component macros
│   │   │   ├── manifest_builder.py
│   │   │   └── renderer.py
│   │   └── validators/       # ValidationEngine (26+ rules, 5 rule sets)
│   └── life-system-builder/  # React + Vite frontend
│       └── src/
│           ├── App.tsx        # Router setup (wouter)
│           ├── components/
│           │   ├── layout/    # AppLayout, AppSidebar, ProjectHeader
│           │   ├── shared/    # StatusBadge, LoadingState, EmptyState, ErrorState
│           │   ├── pipeline/  # StageCard
│           │   ├── output/    # JsonViewer (interactive collapsible tree)
│           │   ├── validation/# DefectList, ValidationSummary
│           │   └── preview/   # DocumentFrame (iframe wrapper)
│           └── pages/
│               ├── ProjectsPage.tsx    # Dashboard grid
│               ├── NewProjectPage.tsx  # Project creation form
│               ├── PipelinePage.tsx    # Stage runner with "Run All"
│               ├── StagePage.tsx       # JSON output inspector
│               ├── ValidationPage.tsx  # Defects + verdict
│               ├── PreviewPage.tsx     # Document iframe preview
│               └── ExportPage.tsx      # HTML + JSON download
└── lib/
    ├── api-client-react/      # Generated React Query hooks + types
    │   └── src/
    │       ├── custom-fetch.ts  # Fetch with deepCamelKeys transformer
    │       └── generated/       # Orval-generated (DO NOT EDIT)
    └── api-spec/              # OpenAPI specification
```

## Routes

| Path | Page |
|------|------|
| `/` | Redirects to `/projects` |
| `/projects` | Dashboard — all project cards |
| `/projects/new` | Create new project form |
| `/projects/:id` | Pipeline page (default tab) |
| `/projects/:id/stage/:stage` | Stage JSON output inspector |
| `/projects/:id/validation` | Validation audit results |
| `/projects/:id/preview` | Document iframe preview |
| `/projects/:id/export` | Download HTML + JSON bundle |

## Pipeline Stages (in order)

1. `system-architecture` — Maps life event to operating system structure
2. `worksheet-system` — Generates task worksheets and checklists
3. `layout-mapping` — Assigns document archetypes to worksheets
4. `render-blueprint` — Produces render manifest with page content
5. `validation-audit` — Compiler-style validation of all stage outputs

## API Endpoints

- `GET /api/healthz` — Health check
- `GET /api/projects` — List all projects
- `POST /api/projects` — Create project (body: `{title, lifeEvent, context}`)
- `GET /api/projects/:id` — Get project
- `GET /api/projects/:id/stages` — List stage outputs
- `GET /api/projects/:id/stages/:stage` — Get specific stage output
- `POST /api/pipeline/:id/run/:stage` — Run a specific pipeline stage
- `POST /api/pipeline/:id/validate` — Run validation audit
- `POST /api/render/:id` — Render project to HTML
- `GET /api/export/:id` — Get export bundle (HTML + JSON)

## CSS Design Language

- **Sidebar**: near-black warm (`hsl(30 22% 10%)`)
- **Background**: warm off-white paper (`hsl(36 22% 96%)`)
- **Accent**: muted gold (`hsl(36 40% 47%)`)
- **Radius**: 3px (institutional, not SaaS)
- **Fonts**: Inter (sans), Georgia (serif), Menlo (mono)
- Status colors: green=complete/pass, red=failed/fail, amber=conditional/warning, grey=pending
