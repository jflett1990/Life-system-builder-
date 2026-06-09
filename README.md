# Tutorial Builder

Turns a request like **"Build a SaaS landing page with Next.js and Tailwind"** into a complete, structured tutorial — framed goals, a step-by-step outline, detailed walkthroughs with code snippets, verification checkpoints, debugging notes, and a print-ready HTML/PDF/DOCX handbook.

The builder works for any topic, but it is **optimized for coding and software work**: vibe-coding sessions, project walkthroughs, "teach me how to build X" flows, debugging guides, and build/deploy runbooks.

---

## What it produces

Every generated tutorial follows a consistent structure:

1. Tutorial title + goal (what you will build or learn)
2. Best-fit audience / skill level
3. Prerequisites and tools/setup required
4. Step-by-step walkthrough (one chapter per module, with numbered substeps)
5. Code snippets and implementation examples (toggleable)
6. Checkpoints — how to verify progress at every step
7. Common mistakes / debugging notes
8. Final outcome + suggested next improvements

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  artifacts/life-system-builder   (React + Vite, port via $PORT) │
│   src/pages/         — tutorial intake, pipeline, preview,      │
│                         validation, export                      │
│   src/components/    — shared UI, pipeline, validation, preview │
│   src/hooks/         — useProjectWithStages, useStagePolling    │
│   src/lib/           — stages.ts (stage labels), error.ts       │
└────────────────────────┬────────────────────────────────────────┘
                          │  Vite proxy  /api → localhost:8080
┌────────────────────────▼────────────────────────────────────────┐
│  artifacts/api-server   (Python FastAPI, port 8080)             │
│   api/routes/        — projects, pipeline, render, export       │
│   contracts/         — LLM prompt contracts per stage           │
│   services/          — ProjectService, PipelineService,         │
│                         RenderService, ValidationService,       │
│                         ExportService                           │
│   models_integration/ — ModelService (Anthropic / OpenAI),      │
│                          JSON repair, output validator          │
│   render/            — Jinja2 renderer, ManifestBuilder,        │
│                          CSS design token system                │
│   validators/        — compiler-style cross-stage checks        │
│   storage/           — SQLAlchemy models + migration runner     │
└────────────────────────┬────────────────────────────────────────┘
                          │  SQLAlchemy ORM
┌────────────────────────▼────────────────────────────────────────┐
│  PostgreSQL or SQLite  (via DATABASE_URL)                       │
│   projects, stage_outputs, validation_results,                  │
│   render_artifacts, branding_profiles, schema_migrations        │
└─────────────────────────────────────────────────────────────────┘
```

> Note: the frontend package directory is still named `artifacts/life-system-builder`
> (`@workspace/life-system-builder`) from the product's previous incarnation. The
> internal pipeline stage names were also kept stable across the pivot to avoid
> churning the persistence layer.

---

## The Tutorial Pipeline

Conceptually the pipeline has six phases; internally it runs as nine upstream-gated stages (internal stage names in parentheses):

| Phase | Stage(s) | Purpose |
|-------|----------|---------|
| 1. **Tutorial Framing** | `system-architecture` | Interprets the request — goal, audience, prerequisites, stack, modules, milestones, verifiable success criteria |
| 2. **Stack Research** | `tutorial-research` | Grounds the tutorial in verifiable facts — version baselines, key commands with expected outputs, common errors with fixes, canonical references; every downstream stage consumes this research |
| 3. **Tutorial Outline** | `document-outline` | Full blueprint — every step title, every checkpoint/exercise sheet, the dependency chain, ground rules |
| 4. **Tutorial Detail Mapping** | `chapter-expansion`, `chapter-worksheets`, `appendix-builder` | Per-step walkthroughs (substeps, code, expected outputs, debugging notes), verification checklists & exercises, and a reference appendix (glossary, getting help, key resources) |
| 5. **Render Blueprint** | `layout-mapping`, `render-blueprint` | Document layout architecture and the render instruction set (CSS tokens, directives, print spec) |
| 6. **Validation Audit** | `validation-audit` | Compiler-style audit — section completeness, cross-stage references, prerequisite ordering, research grounding, render-readiness |

The research stage marks every fact with a confidence level; low-confidence facts surface as `open_questions` so step writers know exactly what to verify rather than inventing precision.

Pipeline execution is sequential and upstream-gated. Each stage is independently re-runnable (`force=true`); results are persisted between runs. A deterministic (non-LLM) validation engine can also be run at any time via `POST /api/pipeline/{id}/validate`.

---

## Primary use cases

- **Vibe coding** — turn a fuzzy "I want to build X" into a concrete, ordered build plan with checkpoints
- **Coding tutorials** — e.g. "Create a Discord bot with Python", "Build a CRUD app with Supabase"
- **Project walkthroughs** — full builds with module-by-module hand-offs
- **Debugging / deploy flows** — e.g. "Walk me through deploying a FastAPI app"

Tutorial requests support structured controls: skill level, tutorial type (overview / hands-on build / debugging / architecture / deployment), stack, platform, depth, code snippets on/off, output style, and constraints (time budget, preferred tools, things to avoid).

---

## Document Rendering

The renderer is a pure structured-data → HTML transformation (no LLM):

1. **ManifestBuilder** reads all completed stage outputs and produces an ordered page manifest (cover, TOC, dashboard, quick-start, per-step chapters, checkpoint sheets, appendix)
2. **Renderer** iterates the manifest through Jinja2 templates per page archetype
3. Output is a single self-contained HTML file with embedded CSS, paginated by Pagedjs
4. Theme colors are chosen per topic category (web/frontend, backend, DevOps, AI/ML) by the render-blueprint stage

Exports: **PDF** (headless Chromium), **DOCX** (heading styles + fill-in checkpoint sheets), **ZIP bundle**, standalone **HTML**, and per-stage **JSON**.

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm 9+
- PostgreSQL (or set `DATABASE_URL` to a SQLite path for local dev: `sqlite:///./life_system.db`)

### Backend

```bash
cd artifacts/api-server
pip install -r requirements.txt
DATABASE_URL=sqlite:///./life_system.db \
ANTHROPIC_API_KEY=your_key \
python3 main.py
# Server starts on port 8080
```

The default model provider is Anthropic (`core/config.py`). To use OpenAI instead, set `AI_INTEGRATIONS_OPENAI_API_KEY` + `AI_INTEGRATIONS_OPENAI_BASE_URL` and `MODEL_PROVIDER=openai`. CRUD and the UI work without any API key; only stage generation needs one.

### Frontend

```bash
pnpm install
PORT=25676 BASE_PATH=/ pnpm --filter @workspace/life-system-builder run dev
# Vite proxies /api/* to localhost:8080 automatically
```

---

## Sample tutorial prompts

See `docs/tutorial-test-prompts.md`. Examples:

- Build a SaaS landing page with Next.js and Tailwind
- Create a Discord bot with Python
- Build a CRUD app with Supabase
- Walk me through deploying a FastAPI app
- Build a Chrome extension for tab management
- Show me how to make an AI chat app with streaming responses

---

## API Reference

All routes are prefixed with `/api`.

### Projects (tutorials)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects` | List all tutorials |
| `POST` | `/projects` | Create a tutorial (title, topic, skillLevel, tutorialType, stack, platform, depth, includeCode, outputStyle, constraints, context) |
| `GET` | `/projects/{id}` | Get tutorial |
| `PATCH` | `/projects/{id}` | Update tutorial |
| `DELETE` | `/projects/{id}` | Delete tutorial |
| `POST` | `/projects/{id}/duplicate` | Duplicate tutorial (fresh pipeline) |
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
| `POST` | `/render/{id}` | Render tutorial → HTML |
| `GET` | `/render/{id}` | Get cached render metadata |
| `GET` | `/render/{id}/preview` | HTML preview (re-renders) |
| `GET` | `/export/{id}` | Export bundle (HTML + JSON) |
| `GET` | `/export/{id}/download` | Download zip bundle |
| `GET` | `/export/{id}/pdf` | Download PDF (headless Chromium) |
| `GET` | `/export/{id}/docx` | Download editable Word document |
| `GET` | `/export/{id}/html` | Download HTML file |
| `GET` | `/export/{id}/json` | Download combined JSON |
| `GET` | `/export/{id}/json/{stage}` | Download single-stage JSON |
| `GET` | `/export/{id}/manifest` | Bundle manifest metadata |

---

## Database Migrations

Append-only migration runner in `artifacts/api-server/storage/migrations.py`. Migrations run automatically at startup. Migration `m010_pivot_projects_to_tutorials` renames `projects.life_event` → `projects.topic` and adds the tutorial request columns (`skill_level`, `tutorial_type`, `stack`, `platform`, `depth`, `include_code`, `output_style`, `constraints`).

To add a migration, append to the `MIGRATIONS` list:

```python
MIGRATIONS: list[tuple[int, str, MigrationFn]] = [
    # existing entries...
    (11, "describe_what_this_does", _m011_your_fn),
]
```

---

## Testing

```bash
# Backend unit tests
cd artifacts/api-server && python3 -m pytest tests/ -v

# Root typecheck
pnpm run typecheck

# Regenerate the API client after editing lib/api-spec/openapi.yaml
pnpm --filter @workspace/api-spec run codegen
```
