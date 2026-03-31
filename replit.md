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
- `ExportService` → `RenderService` + `PipelineService` (zip packaging — see Export Layer below)

`services/llm_client.py` is **deprecated** — all model calls now go through `models_integration.ModelService`.

## Export Layer (`services/export_service.py`)

Produces downloadable file packages from rendered pipeline outputs. All zip operations are in-memory — no temp files or filesystem writes.

### Bundle Structure

```
LSB-{id:05d}-export.zip
├── manifest.json          — bundle metadata + file index (bundle_id, document_id, stages, pdf_status)
├── html/
│   └── document.html      — self-contained, print-ready HTML (styles embedded)
├── json/
│   └── {stage}.json       — one file per completed pipeline stage
└── pdf/
    └── PENDING.txt        — honest PDF notice + instructions for headless generation
```

### Export Endpoints (`api/routes/export.py`)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/api/export/{id}` | `ExportBundle` JSON | Existing — used by frontend ExportPage |
| GET | `/api/export/{id}/download` | `application/zip` | Full bundle download |
| GET | `/api/export/{id}/html` | `text/html` attachment | HTML document only |
| GET | `/api/export/{id}/json` | `application/json` attachment | All stages combined |
| GET | `/api/export/{id}/json/{stage}` | `application/json` attachment | Single stage JSON |
| GET | `/api/export/{id}/manifest` | JSON | Bundle metadata preview (no file content) |

### PDF Hook Point

`ExportService.export_pdf()` raises `NotImplementedError` with a clear message. The HTML pipeline produces print-ready output — no content changes are needed when a PDF renderer (WeasyPrint, Playwright, headless Chrome) is integrated. The zip bundle's `pdf/PENDING.txt` gives complete instructions for browser-based and headless PDF generation.

### Key Classes

| Class | File | Responsibility |
|-------|------|---------------|
| `ExportService` | `services/export_service.py` | Orchestrates render + packaging; exposes per-format methods |
| `ZipPackageBuilder` | `services/export_service.py` | In-memory zip builder — writes manifest, html/, json/, pdf/ |
| `BundleManifest` | `services/export_service.py` | Dataclass serialized as `manifest.json` inside the zip |
| `ExportError` | `services/export_service.py` | Base export error |
| `ExportNotReadyError` | `services/export_service.py` | Raised when no stages are complete (→ HTTP 400) |

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
| `schema_retry_attempts` | `2` | Additional attempts after Pydantic schema failure |

## Stage Output Schemas (`schemas/stage_outputs/`)

Every pipeline stage has a Pydantic model for strict output validation.

| Stage | Schema Class | Key Required Fields |
|-------|-------------|-------------------|
| `system_architecture` | `SystemArchitectureOutput` | `system_name`, `life_event`, `operating_premise`, `system_objective`, `control_domains` (min 1), `key_roles` (min 1), `success_criteria` (min 1) |
| `worksheet_system` | `WorksheetSystemOutput` | `worksheet_system_name`, `worksheets` (min 1), `completion_sequence` (min 1) |
| `layout_mapping` | `LayoutMappingOutput` | `document_title`, `document_subtitle`, `version`, `total_sections`, `print_structure`, `sections` (min 1) |
| `render_blueprint` | `RenderBlueprintOutput` | `blueprint_name`, `theme` (non-empty dict), `render_directives` (min 1), `page_count_estimate` |
| `validation_audit` | `ValidationAuditOutput` | `audit_passed`, `total_issues`, `stages_audited` (min 1), `issues`, `stage_summaries` (min 1), `render_ready`, `export_ready`, `audit_summary` |

All schemas use `ConfigDict(extra="allow")` — unknown fields are preserved but not required.

`WorksheetSystemOutput` includes a `model_validator(mode="before")` that auto-unwraps common nesting patterns the model may produce (e.g. `{"worksheet_system": {...}}` → top-level fields).

## Critical Architecture Notes

### `gpt-5.2` is a Reasoning Model

`gpt-5.2` (used via Replit AI Integrations) is a reasoning model (o1/o3 family). This has two important implications:

1. **Never set `max_completion_tokens`**: Reasoning models use completion tokens for internal "thinking" steps. Setting `max_completion_tokens=8192` caused the model to exhaust its entire token budget on reasoning and return empty content (`len=0, finish_reason=length`). The fix is to omit `max_completion_tokens` entirely and let the model use its natural output budget.

2. **Responses can take 2-3 minutes**: Complex stages like `worksheet_system` may take 100-120 seconds to respond. The 120s timeout in `model_timeout_s` is appropriate; do not lower it.

### Upstream Context Truncation

Large upstream stage outputs are capped at `_MAX_UPSTREAM_CHARS = 8000` characters per stage in `core/prompt_assembler.py`. This prevents prompt bloat from exceeding the model's input context budget. The `system_architecture` output for complex life events can be 12,000-15,000 characters; the cap truncates it to ~8,000 chars (~2,000 tokens).

### Schema Failure Raw Output Preservation

`ModelService.generate_structured_output()` does **not** raise `OutputValidationError`. Instead, it logs the error and returns the `(StructuredOutput, ParseResult)` tuple. `PipelineService.run_stage()` is responsible for:
1. Calling `stage_row.set_raw_output(structured.raw_text)` immediately after the model call
2. Checking `parse_result.success` to decide whether to mark the stage `complete` or `schema_failed`

This guarantees raw model output is always saved to `raw_model_output` column, even when schema validation fails.

### ParseResult

`models_integration/parser.py` — `StageOutputParser.parse()` returns a `ParseResult` dataclass:
- `success` — True if Pydantic validation passed
- `parsed_data` — schema-coerced dict (None on failure)
- `raw_data` — unvalidated dict from JSON extraction
- `raw_text` — original model response string
- `validation_errors` — list of human-readable Pydantic error messages
- `for_retry_prompt()` — formats errors for the correction conversation
- `for_error_message()` — formats errors for `stage_output.error_message`

### Three-Layer Retry System

```
Layer 1 — API transport retries (model_max_retries=3)
  ↓ fail: ModelProviderError
Layer 2 — JSON repair (model_repair_attempts=1)
  Local repair strategies → LLM repair prompt if all local fail
  ↓ fail: ModelOutputError
Layer 3 — Schema correction passes (schema_retry_attempts=2)
  On Pydantic failure: send [original + bad response + correction user msg] → retry
  ↓ fail: OutputValidationError (strict) or log warning (lenient)
```

### Stage Failure Status Values

| `status` | Meaning |
|----------|---------|
| `pending` | Not started |
| `running` | In progress |
| `complete` | Success — `json_output` has validated data |
| `failed` | API or JSON extraction failure |
| `schema_failed` | JSON parsed but Pydantic schema rejected it after all retries |

### Dual Output Storage

| Column | Content |
|--------|---------|
| `json_output` | Schema-validated dict (what renders/exports use) |
| `raw_model_output` | Original model response string verbatim (for debugging) |

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
- `PATCH /api/projects/:id` — Update project
- `DELETE /api/projects/:id` — Delete project
- `POST /api/projects/:id/duplicate` — Duplicate project (fresh pipeline, same metadata)
- `GET /api/projects/:id/stages` — List stage outputs
- `GET /api/projects/:id/stages/:stage` — Get specific stage output
- `GET /api/projects/:id/summary` — Pipeline progress summary
- `POST /api/pipeline/:id/run/:stage` — Run stage (`?force=true` to re-run even if complete)
- `POST /api/pipeline/:id/run-all` — Run all pending stages
- `POST /api/pipeline/:id/validate` — Run validation audit (persists result)
- `GET /api/pipeline/:id/validate` — Get persisted validation result (no re-run)
- `POST /api/render/:id` — Render project to HTML (caches result)
- `GET /api/render/:id` — Get cached render metadata (`CachedRenderInfo`: page_count, document_title, updated_at)
- `GET /api/render/:id/preview` — HTML preview (always re-renders)
- `GET /api/export/:id` — Get export bundle JSON (HTML + all stage JSON)
- `GET /api/export/:id/download` — Download zip bundle
- `GET /api/export/:id/html` — Download HTML file attachment
- `GET /api/export/:id/json` — Download combined stage JSON
- `GET /api/export/:id/json/:stage` — Download single-stage JSON
- `GET /api/export/:id/manifest` — Bundle manifest metadata

## Frontend Shared Utilities

Added in hardening pass — use these, never inline equivalents:

| File | Export | Use For |
|------|--------|---------|
| `src/lib/stages.ts` | `PIPELINE_STAGES`, `STAGE_META`, `getStageLabel()`, `getStageMeta()` | All stage metadata — single source of truth |
| `src/lib/error.ts` | `extractApiError(error)` | Extract human-readable error string from any API error |
| `src/hooks/use-project.ts` | `useProjectWithStages(id)`, `useStagePolling(id)` | Project + stages combined query; 3s polling when any stage is running |
| `src/components/shared/ErrorBoundary.tsx` | `<ErrorBoundary fallback={...}>` | Wrap any component that might throw |

## API Client Hooks (Extended)

Hooks added beyond Orval codegen output (in `lib/api-client-react/src/generated/api.ts`):

| Hook | Added Parameter | Notes |
|------|----------------|-------|
| `useRunStage` | `force?: boolean` → `?force=true` query param | Force re-run of already-complete stage |
| `useGetValidationResult` | — | GET persisted validation result (no re-run) |
| `useDuplicateProject` | — | POST duplicate → navigates to new project |

## CSS Design Language

- **Sidebar**: near-black warm (`hsl(30 22% 10%)`)
- **Background**: warm off-white paper (`hsl(36 22% 96%)`)
- **Accent**: muted gold (`hsl(36 40% 47%)`)
- **Radius**: 3px (institutional, not SaaS)
- **Fonts**: Inter (sans), Georgia (serif), Menlo (mono)
- Status colors: green=complete/pass, red=failed/fail, amber=conditional/warning, grey=pending
