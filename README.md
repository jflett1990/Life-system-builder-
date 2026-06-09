# Tutorial Builder

Creates structured tutorials, coding walkthroughs, project build guides, debugging flows, architecture walkthroughs, and deployment guides from a user prompt. The default product bias is software: vibe coding, implementation tutorials, “teach me how to build X” flows, project walkthroughs, and practical engineering runbooks.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  artifacts/life-system-builder   (React + Vite, port via $PORT) │
│   src/pages/         — one page per app section                 │
│   src/components/    — shared UI, pipeline, validation, preview │
│   src/hooks/         — useProjectWithStages, useStagePolling    │
│   src/lib/           — stages.ts (single source of truth),      │
│                         error.ts (error extraction utility)     │
└────────────────────────┬────────────────────────────────────────┘
                          │  Vite proxy  /api → localhost:8080
┌────────────────────────▼────────────────────────────────────────┐
│  artifacts/api-server   (Python FastAPI, port 8080)             │
│   api/routes/        — projects, pipeline, render, export       │
│   services/          — ProjectService, PipelineService,         │
│                         RenderService, ValidationService,       │
│                         ExportService                           │
│   models_integration/ — ModelService, OpenAI provider,          │
│                          JSON repair, output validator          │
│   render/            — Jinja2 renderer, ManifestBuilder,        │
│                          CSS design token system                │
│   validators/        — compiler-style cross-stage checks        │
│   storage/           — SQLAlchemy models + migration runner     │
└────────────────────────┬────────────────────────────────────────┘
                          │  SQLAlchemy ORM
┌────────────────────────▼────────────────────────────────────────┐
│  PostgreSQL  (via DATABASE_URL)                                  │
│   projects, stage_outputs, validation_results,                  │
│   render_artifacts, branding_profiles, schema_migrations        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tutorial Generation Pipeline

Each stage consumes the outputs of all previous stages as structured context.

| # | Stage | Purpose |
|---|-------|---------|
| 1 | **Tutorial Framing** | Interprets the request, goal, audience, prerequisites, stack, constraints, and success criteria |
| 2 | **Tutorial Outline** | Generates modules, setup flow, milestones, exercises, and learning sequence |
| 3 | **Tutorial Detail Mapping** | Expands each module with implementation steps, examples, checkpoints, and debugging notes |
| 4 | **Exercises & Checklists** | Produces labs, verification checklists, code-review prompts, and deployment/debugging rubrics |
| 5 | **Reference Builder** | Adds glossary, tools/resources, common blockers, and next-step extension material |
| 6 | **Delivery Layout** | Maps tutorial content into a printable/renderable document structure |
| 7 | **Render Blueprint** | Produces theme tokens, component directives, and print specifications |
| 8 | **Validation Audit** | Checks structural completeness, prerequisite coherence, tutorial flow, checkpoints, and render readiness |

Pipeline execution: sequential, upstream-gated. Each stage is independently re-runnable (`force=true`). Results are persisted to the database between runs.

---

## Document Rendering

The renderer is a pure structured-data → HTML transformation (no LLM):

1. **ManifestBuilder** reads all completed stage outputs and produces an ordered page manifest
2. **Renderer** iterates the manifest through Jinja2 templates per page archetype
3. Output is a single self-contained HTML file with embedded CSS using the design token system
4. CSS uses the **US Letter** page format (215.9×279.4mm, 20mm margins) and `@page` rules for print
5. Edition overrides inject exactly 4 CSS custom properties (`--color-cover-bg`, `--color-accent`, etc.)

---


## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm 9+
- PostgreSQL, or set `DATABASE_URL` to a SQLite path for local dev such as `sqlite:///./life_system.db`

### Backend

```bash
cd artifacts/api-server
pip install -r requirements.txt
DATABASE_URL=sqlite:///./life_system.db \
AI_INTEGRATIONS_OPENAI_API_KEY=your_key \
AI_INTEGRATIONS_OPENAI_BASE_URL=https://api.openai.com/v1 \
python main.py
# Server starts on port 8080
```

### Frontend

```bash
pnpm install
export PORT=25676 BASE_PATH=/
pnpm --filter @workspace/life-system-builder run dev
# Dev server starts on the port in $PORT (default 25676)
# Vite proxies /api/* to localhost:8080 automatically
```

---

## Primary Use Cases

- Build a SaaS landing page with Next.js and Tailwind
- Create a Discord bot with Python
- Build a CRUD app with Supabase
- Walk through deploying a FastAPI app
- Build a Chrome extension for tab management
- Create an AI chat app with streaming responses
- Debug a failing deployment, flaky test, or broken API integration
- Explain a project architecture and how to extend it safely

---

## API Reference

All routes are prefixed with `/api`.

### Projects
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects` | List all projects |
| `POST` | `/projects` | Create a tutorial project |
| `GET` | `/projects/{id}` | Get project |
| `PATCH` | `/projects/{id}` | Update project |
| `DELETE` | `/projects/{id}` | Delete project |
| `POST` | `/projects/{id}/duplicate` | Duplicate project (fresh pipeline) |
| `GET` | `/projects/{id}/stages` | List stage outputs |
| `GET` | `/projects/{id}/stages/{stage}` | Get single stage output |
| `GET` | `/projects/{id}/summary` | Pipeline progress summary |

### Pipeline
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/pipeline/{id}/run/{stage}` | Run a stage (`?force=true` to re-run) |
| `POST` | `/pipeline/{id}/run-all` | Run full pipeline |
| `POST` | `/pipeline/{id}/validate` | Run validation engine |
| `GET` | `/pipeline/{id}/validate` | Get persisted validation result |

### Render & Export
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/render/{id}` | Render project → HTML |
| `GET` | `/render/{id}` | Get cached render metadata |
| `GET` | `/render/{id}/preview` | HTML preview (re-renders) |
| `GET` | `/export/{id}` | Export bundle (HTML + JSON) |
| `GET` | `/export/{id}/download` | Download zip bundle |
| `GET` | `/export/{id}/html` | Download HTML file |
| `GET` | `/export/{id}/json` | Download combined JSON |
| `GET` | `/export/{id}/json/{stage}` | Download single-stage JSON |
| `GET` | `/export/{id}/manifest` | Bundle manifest metadata |

---

## Database Migrations

Append-only migration runner in `artifacts/api-server/storage/migrations.py`. Migrations run automatically at startup. To add a migration, append to the `MIGRATIONS` list:

```python
MIGRATIONS: list[tuple[int, str, MigrationFn]] = [
    # existing entries...
    (7, "describe_what_this_does", _m007_your_fn),
]
```

---

## PDF Export

Server-side PDF rendering uses the export service when Playwright/Chromium is available. The HTML output is also print-ready, so the fallback path is to open the exported HTML in a browser and use **File -> Print -> Save as PDF**.

When improving PDF behavior in the future, the hook is `ExportService.export_pdf()` in `services/export_service.py`.
