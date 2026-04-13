# CLAUDE.md — Life System Builder

AI assistant guidance for working in this repository. Read this before making any changes.

---

## What This Project Does

**Life System Builder** converts a life event (caregiving, estate planning, job loss, divorce, etc.) into a structured operational control system — a print-ready manual that tells the user exactly what decisions to make, who makes them, and in what order.

The core loop:
1. User creates a **Project** describing their life event
2. A **Five-Stage LLM Pipeline** generates the system definition, document outline, chapter content, worksheets, and appendices
3. A **Render Service** produces paged HTML (CSS print media) → PDF-ready output
4. The user exports a zip with HTML, JSON, and per-stage artifacts

---

## Repository Layout

```
/
├── artifacts/
│   ├── api-server/          # Python FastAPI backend (port 8080)
│   ├── life-system-builder/ # React + Vite frontend
│   └── mockup-sandbox/      # UI component sandbox (standalone)
├── lib/
│   ├── api-client-react/    # Orval-generated React Query hooks
│   ├── api-spec/            # OpenAPI spec + Orval codegen config
│   ├── api-zod/             # Zod schema definitions
│   ├── db/                  # Drizzle ORM schema (TypeScript)
│   ├── integrations-openai-ai-react/   # OpenAI hooks for React
│   └── integrations-openai-ai-server/  # OpenAI client for Node
├── scripts/                 # Post-merge hook + utilities
├── docs/                    # Additional documentation
├── contracts/               # JSON prompt contracts (api-server)
├── pnpm-workspace.yaml      # pnpm monorepo config
├── pyproject.toml           # Python deps (UV format)
├── tsconfig.base.json       # Shared TS config
└── replit.nix / .replit     # Replit deployment config
```

---

## Technology Stack

### Backend (`artifacts/api-server/`)
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115+ |
| Server | Uvicorn 0.30+ |
| ORM | SQLAlchemy 2.0+ |
| Validation | Pydantic v2 |
| AI | OpenAI Python SDK 1.0+ |
| Templating | Jinja2 3.1+ |
| Doc export | python-docx 1.1+, Playwright 1.40+ |
| Async I/O | aiofiles 23.0+ |

### Frontend (`artifacts/life-system-builder/`)
| Layer | Technology |
|-------|-----------|
| Framework | React 19.1.0 (pinned) |
| Build | Vite 7.3+ |
| Styling | Tailwind CSS v4 + shadcn/ui + Radix UI |
| State | TanStack React Query 5 |
| Forms | react-hook-form 7 + Zod |
| Routing | Wouter 3 |
| Animation | Framer Motion 12 |
| API client | Orval-generated hooks (`@workspace/api-client-react`) |

### Shared Libraries (`lib/`)
- **TypeScript 5.9**, pnpm 9 monorepo, Drizzle ORM (schema-only)
- Supply-chain security: `minimumReleaseAge = 1440` minutes in `.npmrc`

### Database
- **Local dev**: SQLite 3 (`sqlite:///./life_system.db`)
- **Production (Replit)**: PostgreSQL 16
- Auto-detected at startup; migrations run automatically

---

## Running the Project Locally

### Prerequisites
```bash
# Node.js 24+, Python 3.11+, pnpm 9+
pnpm install
pip install -r artifacts/api-server/requirements.txt
```

### Backend
```bash
cd artifacts/api-server
DATABASE_URL=sqlite:///./life_system.db \
  AI_INTEGRATIONS_OPENAI_API_KEY=sk-... \
  AI_INTEGRATIONS_OPENAI_BASE_URL=https://api.openai.com/v1 \
  python main.py
# Runs on http://localhost:8080
```

### Frontend
```bash
cd artifacts/life-system-builder
PORT=3000 pnpm run dev
# Proxies /api → http://localhost:8080
```

### Tests
```bash
cd artifacts/api-server
python -m pytest tests/ -v
```

### Type Checking
```bash
# Root (all workspaces)
pnpm run typecheck

# Frontend only
cd artifacts/life-system-builder && pnpm run typecheck

# Backend (none — Python uses Pydantic runtime validation)
```

---

## Environment Variables

### Required
| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | `sqlite:///./path.db` or PostgreSQL DSN |
| `AI_INTEGRATIONS_OPENAI_API_KEY` | OpenAI API key |
| `AI_INTEGRATIONS_OPENAI_BASE_URL` | `https://api.openai.com/v1` or proxy |

### Optional
| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_MODEL` | `gpt-5.2` | Default model for all stages |
| `PLANNER_MODEL` | `gpt-5.4` | Reasoning-heavy stages |
| `EXECUTOR_MODEL` | `gpt-5.4` | Content generation stages |
| `PORT` | `8080` | API server port |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `API_KEY` | — | Enables API key auth on mutation endpoints |
| `ALLOWED_ORIGINS` | — | Comma-separated CORS origins |
| `CHAPTER_EXPANSION_WORKERS` | `4` | Concurrency for chapter expansion |
| `MODEL_MAX_RETRIES` | `3` | LLM call retry limit |
| `MODEL_TIMEOUT_S` | `300` | LLM call timeout (seconds) |
| `SCHEMA_RETRY_ATTEMPTS` | `2` | Post-Pydantic validation retries |

Configuration is loaded via `artifacts/api-server/core/config.py` (pydantic-settings). See `artifacts/api-server/ENVIRONMENT.md` for full details.

---

## Pipeline Architecture

The backend is structured as a sequential, upstream-gated LLM pipeline:

```
Stage 1: system_architecture   → Maps life event → domains, roles, constraints
Stage 2: document_outline      → Blueprint structure (chapters, worksheets)
Stage 3: chapter_expansion     → Narrative + quick-reference rules per chapter
Stage 4: chapter_worksheets    → Task worksheets, trackers, checklists per chapter
Stage 5: appendix_builder      → Domain appendices (glossary, resources)
Stage 6: layout_mapping        → Chapters/worksheets → document layout
Stage 7: render_blueprint      → Page manifest with formatting directives
Stage 8: validation_audit      → Compiler-style structural checks (no LLM)
```

**Key behaviors:**
- Stages must run in order; each checks upstream completion before proceeding
- Any stage can be re-run with `force=true` (idempotent)
- Execution is non-blocking: POST to `/api/pipeline/{id}/run/{stage}` returns immediately with `status: "running"`, then poll `GET /api/projects/{id}/stages` for completion
- Stage results stored in `stage_outputs` table as JSON

**Stage name formats:**
- Backend internal: `snake_case` (e.g., `system_architecture`)
- URL parameters: `snake_case`
- Frontend display: `kebab-case` via `STAGE_HYPHEN_MAP` constant
- Use `normalize_stage_name()` on the backend when converting between formats

---

## Backend Code Layout

```
artifacts/api-server/
├── main.py                  # FastAPI app entry point
├── core/
│   ├── config.py            # pydantic-settings configuration
│   └── database.py          # SQLAlchemy engine + session factory
├── models/                  # SQLAlchemy ORM models
│   ├── project.py
│   ├── stage_output.py
│   ├── validation_result.py
│   ├── render_artifact.py
│   └── branding_profile.py
├── routes/                  # FastAPI route handlers (thin — delegate to services)
├── services/                # Business logic
│   ├── project_service.py
│   ├── pipeline_service.py
│   ├── validation_service.py
│   ├── render_service.py
│   └── export_service.py
├── repositories/            # Data access layer
│   ├── project_repository.py
│   ├── stage_output_repository.py
│   ├── validation_repository.py
│   ├── render_artifact_repository.py
│   └── branding_profile_repository.py
├── pipeline/                # LLM pipeline orchestration
│   ├── orchestrator.py      # PipelineOrchestrator (stage ordering)
│   ├── model_service.py     # ModelService (single LLM entry point)
│   ├── providers/           # BaseModelProvider + OpenAIProvider
│   ├── parser.py            # StageOutputParser (JSON repair + coercion)
│   └── validator.py         # OutputValidator (field-presence checks)
├── validation/              # Compiler-style validation engine
│   ├── engine.py            # ValidationEngine
│   ├── rules/               # Per-stage and cross-stage rule sets
│   └── defects.py           # Defect system (fatal/error/warning/info)
├── render/                  # HTML render pipeline
│   ├── render_service.py
│   ├── manifest_builder.py
│   └── templates/           # Jinja2 templates (per-archetype)
├── storage/
│   └── migrations.py        # Append-only migration runner
├── contracts/               # JSON prompt contracts (11 files)
└── tests/                   # pytest tests
```

**Dependency flow**: Routes → Services → Repositories → ORM models. Never skip layers.

---

## Frontend Code Layout

```
artifacts/life-system-builder/src/
├── App.tsx                  # Router + layout root
├── pages/
│   ├── ProjectsPage.tsx     # Project list
│   ├── NewProjectPage.tsx   # Create project form
│   ├── PipelinePage.tsx     # Stage overview
│   ├── StagePage.tsx        # Single stage detail
│   ├── PreviewPage.tsx      # HTML render preview
│   ├── ValidationPage.tsx   # Validation report
│   └── ExportPage.tsx       # Export controls
├── components/
│   ├── layout/              # AppLayout, AppSidebar, ProjectHeader
│   ├── ui/                  # shadcn/ui components (do not hand-edit)
│   └── shared/              # ErrorBoundary, LoadingState, StatusBadge
├── hooks/
│   └── use-project.ts       # Primary data hook (project + stages)
└── lib/
    ├── stages.ts            # PIPELINE_STAGES, STAGE_META, STAGE_HYPHEN_MAP
    └── utils.ts             # cn(), formatting helpers
```

**API calls**: Always use the Orval-generated hooks from `@workspace/api-client-react`. Do not write raw `fetch` calls against `/api` in components.

---

## Database Models

| Model | Table | Key Columns |
|-------|-------|-------------|
| `Project` | `projects` | `id`, `title`, `life_event`, `audience`, `tone`, `context`, `formatting_profile`, `artifact_density`, `status` |
| `StageOutput` | `stage_outputs` | `project_id`, `stage_name`, `status`, `json_output`, `raw_model_output`, `revision_number` |
| `ValidationResultModel` | `validation_results` | `project_id`, `stage_name` (nullable), `verdict`, `blocked_handoff`, `defects_json` |
| `RenderArtifact` | `render_artifacts` | `project_id`, `manifest_json`, `html_bundle_path`, `page_count` |
| `BrandingProfile` | `branding_profiles` | `name`, `primary_color`, `accent_color`, `font_family`, `css_tokens` |

**Relations**: `StageOutput` and `ValidationResult` cascade-delete with `Project`. `RenderArtifact` is upserted (one per project).

**Migrations**: Add new columns via `storage/migrations.py` using `_add_column_if_missing()`. Never drop or rename columns; always add. The runner is append-only and dialect-aware (SQLite ↔ PostgreSQL).

---

## API Reference Summary

Base path: `/api`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness check |
| `GET/POST` | `/projects` | List / create projects |
| `GET/PATCH/DELETE` | `/projects/{id}` | Read / update / delete project |
| `POST` | `/projects/{id}/duplicate` | Clone project |
| `GET` | `/projects/{id}/stages` | List all stage outputs |
| `GET` | `/projects/{id}/stages/{stage}` | Single stage output |
| `POST` | `/pipeline/{id}/run/{stage}` | Run one stage (non-blocking) |
| `POST` | `/pipeline/{id}/run-all` | Queue all stages |
| `POST/GET` | `/pipeline/{id}/validate` | Run / read validation |
| `POST/GET` | `/render/{id}` | Render / read artifact |
| `GET` | `/render/{id}/preview` | HTML preview |
| `GET` | `/export/{id}` | Export metadata |
| `GET` | `/export/{id}/download` | Download zip |
| `GET` | `/export/{id}/html` | HTML bundle |
| `GET` | `/export/{id}/json` | Full JSON export |
| `GET` | `/export/{id}/json/{stage}` | Single-stage JSON |
| `GET` | `/contracts` / `/contracts/{name}` | Contract registry |

**Request/response JSON uses camelCase** (Pydantic `to_camel` alias generator). Internal Python code uses `snake_case`.

**Authentication**: `X-API-Key` header required on mutation endpoints when `API_KEY` env var is set. GET endpoints are always open.

---

## Key Conventions

### Python (Backend)
- Classes: `PascalCase` (`ProjectService`, `PipelineOrchestrator`)
- Functions/methods/variables: `snake_case`
- Files: `snake_case` (`pipeline_service.py`)
- Database tables/columns: `snake_case`
- Pydantic models expose camelCase aliases via `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)`

### TypeScript/React (Frontend)
- React components: `PascalCase` in `.tsx` files
- Hooks: `camelCase` with `use` prefix (`use-project.ts`)
- Constants: `UPPER_SNAKE_CASE` (`PIPELINE_STAGES`, `STAGE_META`)
- General types: `PascalCase`
- File names: `PascalCase.tsx` for components, `kebab-case.ts` for utilities and hooks

### Commit Messages
Follow the project's existing style:
```
Short imperative verb phrase (under 72 chars)

Optional body explaining the why, if non-obvious.
```

---

## Common Development Tasks

### Add a new pipeline stage
1. Create a contract JSON in `artifacts/api-server/contracts/`
2. Add the stage name to `PIPELINE_STAGES` in `lib/` and `stages.ts`
3. Register the stage in `pipeline/orchestrator.py` (ordering + upstream deps)
4. Add a Pydantic output model in `models/`
5. Write validation rules in `validation/rules/`
6. Add migration if new DB columns are needed

### Add a new API endpoint
1. Define the route in `routes/` (thin handler — validate input, call service, return response)
2. Implement business logic in the relevant `services/` file
3. Add DB access in `repositories/` if needed
4. Update `lib/api-spec/` OpenAPI spec, then regenerate client: `cd lib/api-client-react && pnpm run generate`

### Update the OpenAPI client
```bash
cd lib/api-spec
# Edit openapi.json
cd ../api-client-react
pnpm run generate   # Runs Orval codegen
```

### Add a database migration
```python
# In artifacts/api-server/storage/migrations.py
# Append to the migrations list:
{
    "id": "YYYYMMDD_description",
    "sql_sqlite": "ALTER TABLE ... ADD COLUMN ...",
    "sql_postgres": "ALTER TABLE ... ADD COLUMN IF NOT EXISTS ..."
}
```

### Modify render templates
Jinja2 templates live in `artifacts/api-server/render/templates/`. CSS uses paged media (`@page`, `page-break-*`) for print layout. Test with Playwright headless Chrome.

---

## What NOT to Do

- **Do not write raw SQL** — use SQLAlchemy ORM or the migration helpers
- **Do not call `/api` with raw fetch in frontend** — use Orval-generated hooks
- **Do not skip upstream stage checks** — the pipeline enforcer is strict; stages require prior stages to be `completed`
- **Do not edit files in `components/ui/`** — these are shadcn/ui managed components; replace via shadcn CLI
- **Do not add columns with DROP or RENAME** — migrations are append-only; always add new columns
- **Do not hardcode model names** — read from `config.py` settings (`OPENAI_MODEL`, `PLANNER_MODEL`, etc.)
- **Do not add direct OpenAI calls** — route everything through `ModelService` in `pipeline/model_service.py`
- **Do not install packages younger than 1 day** — `minimumReleaseAge` policy enforced in `.npmrc`

---

## Test Coverage

Tests live in `artifacts/api-server/tests/`:
- `test_content_quality_gates.py` — paragraph structure, action lists, decision guides
- `test_docx_export.py` — DOCX export pipeline + DocxBuilder field mapping
- `test_theme_tokens.py` — theme token extraction from render blueprints

Frontend has no automated tests yet. When testing frontend changes, start the dev server and manually verify the golden path (create project → run pipeline → preview → export).

---

## Further Reading

- `README.md` — Overview, architecture diagram, API reference
- `artifacts/api-server/ENVIRONMENT.md` — Full environment variable docs
- `replit.md` — Replit-specific architecture notes, entity relationships, troubleshooting
- `artifacts/api-server/contracts/` — LLM prompt contracts (JSON, one per stage)
