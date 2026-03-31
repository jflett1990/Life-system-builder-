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

## Persistence Layer

### Database
SQLite for local dev (`sqlite:///./life_system.db`). PostgreSQL in production (via `DATABASE_URL` env var). Config in `core/config.py` — no code change needed to switch.

### Entity Relationships
```
Project 1──* StageOutput         (cascade delete)
Project 1──* ValidationResult    (per-stage rows + one project-level summary)
Project 1──1 RenderArtifact      (unique per project, upserted each render)
BrandingProfile                  (standalone, not yet FK'd to Project)
```

### Models (`models/`)
| Model | Table | Key additions |
|-------|-------|---------------|
| `Project` | `projects` | `formatting_profile`, `artifact_density` |
| `StageOutput` | `stage_outputs` | `preview_text`, `revision_number` |
| `ValidationResultModel` | `validation_results` | `stage_name` (nullable — NULL=summary row, set=per-stage), `result`, `summary`, `defects_json` |
| `RenderArtifact` | `render_artifacts` | `manifest_json`, `html_bundle_path`, `page_count` |
| `BrandingProfile` | `branding_profiles` | Full stub: colors, fonts, logo, CSS token overrides |

### Repository Layer (`repositories/`)
Each repository owns **all SQLAlchemy queries** for its model. Services never touch the ORM directly.

| Repository | Responsibilities |
|-----------|-----------------|
| `ProjectRepository` | `find_all`, `find_by_id`, `insert`, `save`, `delete` |
| `StageOutputRepository` | `find_by_project_and_stage`, `find_all_for_project`, `find_completed_stage_names` |
| `ValidationRepository` | `find_project_summary` (stage_name=NULL), `find_stage_result`, `find_all_stage_results` |
| `RenderArtifactRepository` | `find_by_project`, `insert`, `save`, `delete_for_project` |
| `BrandingProfileRepository` | `find_all`, `find_by_id`, `find_by_name`, `find_default` |

### Services (`services/`)
Services contain business logic only — no SQLAlchemy sessions, no `.query()` calls.
- `ProjectService` → `ProjectRepository`
- `PipelineService` → `StageOutputRepository` + `ProjectService` + **`ModelService`**
- `ValidationService` → `ValidationRepository` + `PipelineService` (persists both summary and per-stage rows)
- `RenderService` → `RenderArtifactRepository` + `PipelineService`

`services/llm_client.py` is **deprecated** — all model calls now go through `models_integration.ModelService`.

## Model Integration Layer (`models_integration/`)

Provider-agnostic abstraction for all LLM calls. Pipeline services import `ModelService` only.

### Architecture

```
BaseModelProvider (ABC, base.py)
  └── OpenAIProvider (openai_provider.py) ← only active provider
        ├── generate_structured_output   — chat completion → JSON extraction → repair → validate
        ├── validate_output              — structural check (no model call)
        └── generate_preview_text        — heuristic extraction → LLM fallback

ModelService (model_service.py)          ← used by PipelineService
  ├── provider factory (reads config.model_provider)
  ├── strict_validation toggle (raises OutputValidationError if True)
  └── wraps all three provider methods with unified logging
```

### Result Types

| Type | Source | Description |
|------|--------|-------------|
| `StructuredOutput` | `base.py` | Frozen dataclass: `data: dict`, `raw_text`, `was_repaired`, `repair_attempts` |
| `PreviewText` | `base.py` | Frozen dataclass: `text`, `stage`, `from_llm` |
| `OutputValidation` | `output_validator.py` | `valid`, `missing_fields`, `empty_fields`, `type_errors`, `.errors` |

### Error Hierarchy

| Error | When raised |
|-------|------------|
| `ModelProviderError` | API failure (rate limit, timeout, auth) |
| `ModelOutputError` | Cannot extract JSON from response after all repair strategies |
| `OutputValidationError` | Parsed JSON missing required contract fields (strict mode only) |

### JSON Repair Strategies (in order)

1. Direct `json.loads` on stripped text
2. Extract from markdown code fence (`` ```json ... ``` ``)
3. Greedy `{...}` regex extraction
4. Brace/bracket balance repair (handles truncated responses — closes unclosed `{` and `[`)
5. Unclosed string repair (`"hello` → `"hello"`) before bracket close
6. Last-comma truncation (drops partial trailing field)
7. One-shot LLM repair prompt if all local strategies fail

### Config Keys

| Key | Default | Purpose |
|-----|---------|---------|
| `model_provider` | `"openai"` | Which provider class to use |
| `openai_model` | `"gpt-5.2"` | Model identifier |
| `model_max_retries` | `3` | API retry attempts with exponential backoff |
| `model_timeout_s` | `120` | Per-request timeout in seconds |
| `model_repair_attempts` | `1` | JSON repair passes before giving up |

### Migrations (`storage/migrations.py`)
Structured migration runner with a `schema_migrations` version table. Dialect-aware — handles both SQLite and PostgreSQL differences (types, constraint syntax, table recreation). Runs at startup via `init_db()`. Add new migrations as functions, append to `MIGRATIONS` list.

Applied migrations:
- 001: Add `formatting_profile`, `artifact_density` to projects
- 002: Add `preview_text` to stage_outputs
- 003: Remove UNIQUE constraint from `validation_results.project_id`; add `stage_name`, `result`, `summary`, `defects_json`
- 004: Create `render_artifacts` table
- 005: Create `branding_profiles` table

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
