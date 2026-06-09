# Tutorial Builder

Turns tutorial requests — coding projects, implementation walkthroughs, deployment guides, debugging flows — into structured, step-by-step tutorials with a full LLM pipeline, schema validation, and print-ready HTML export.

**Default focus:** vibe coding, software tutorials, and "teach me how to build X" flows.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  artifacts/life-system-builder   (React + Vite, port via $PORT) │
│   src/pages/         — tutorial dashboard, intake, pipeline     │
│   src/components/    — shared UI, pipeline, validation, preview │
│   src/hooks/         — useProjectWithStages, useStagePolling    │
│   src/lib/           — stages.ts (pipeline labels), error.ts    │
└────────────────────────┬────────────────────────────────────────┘
                          │  Vite proxy  /api → localhost:8080
┌────────────────────────▼────────────────────────────────────────┐
│  artifacts/api-server   (Python FastAPI, port 8080)             │
│   api/routes/        — projects, pipeline, render, export       │
│   services/          — ProjectService, PipelineService,         │
│                         RenderService, ValidationService,       │
│                         ExportService                           │
│   contracts/v1/      — stage prompt contracts (tutorial copy)   │
│   render/            — Jinja2 renderer, ManifestBuilder, CSS      │
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

## Eight-Stage Tutorial Pipeline

Each stage consumes the outputs of all previous stages as structured context. Internal stage keys are unchanged for compatibility; user-facing labels map to tutorial semantics.

| # | Stage (internal) | User-facing label | Purpose |
|---|------------------|-------------------|---------|
| 1 | `system_architecture` | **Tutorial Framing** | Goal, audience, prerequisites, stack, constraints |
| 2 | `document_outline` | **Tutorial Outline** | Major modules, setup, milestones, learning flow |
| 3 | `chapter_expansion` | **Step Detail Mapping** | Substeps, code examples, checkpoints per module |
| 4 | `chapter_worksheets` | **Implementation Examples** | Hands-on exercises, command refs, code worksheets |
| 5 | `appendix_builder` | **Reference & Troubleshooting** | Glossary, common mistakes, resources |
| 6 | `layout_mapping` | **Delivery Layout** | Section ordering and print architecture |
| 7 | `render_blueprint` | **Render Blueprint** | Typography, code styling, page manifest |
| 8 | `validation_audit` | **Validation Audit** | Structural completeness and consistency checks |

Pipeline execution is sequential and upstream-gated. Each stage is independently re-runnable (`force=true`). Results persist to the database between runs.

---

## Tutorial Output Structure

Generated tutorials follow a consistent shape:

1. Tutorial title
2. Goal / what the learner will build
3. Best-fit audience / skill level
4. Prerequisites
5. Tools / setup required
6. Step-by-step walkthrough (per module)
7. Code snippets and implementation examples
8. Checkpoints / how to verify progress
9. Common mistakes / debugging notes
10. Final outcome
11. Suggested next improvements / extensions

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm 9+
- PostgreSQL (or SQLite for local dev: `sqlite:///./tutorial_builder.db`)

### Backend

```bash
cd artifacts/api-server
pip install -r requirements.txt
DATABASE_URL=sqlite:///./tutorial_builder.db \
AI_INTEGRATIONS_OPENAI_API_KEY=your_key \
AI_INTEGRATIONS_OPENAI_BASE_URL=https://api.openai.com/v1 \
python main.py
# Server starts on port 8080
```

### Frontend

```bash
pnpm install
pnpm --filter @workspace/life-system-builder run dev
# Dev server starts on the port in $PORT (default 25676)
# Vite proxies /api/* to localhost:8080 automatically
```

### Build & typecheck

```bash
pnpm install
pnpm run build
```

---

## Primary Use Cases

- **Vibe coding walkthroughs** — "Build a SaaS landing page with Next.js and Tailwind"
- **Framework tutorials** — "Create a Discord bot with Python", "CRUD app with Supabase"
- **Deployment guides** — "Walk me through deploying a FastAPI app"
- **Extension / tooling builds** — "Chrome extension for tab management"
- **AI app tutorials** — "AI chat app with streaming responses"

Example intake fields: skill level, tutorial type, stack, platform, depth, code snippets yes/no, output style, constraints.

---

## Scenario test prompts

- `docs/tutorial-builder-test-prompt.md` — sample Next.js SaaS landing page tutorial request.

---

## API Reference

All routes are prefixed with `/api`.

### Projects
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects` | List all tutorials |
| `POST` | `/projects` | Create a tutorial (`lifeEvent` = primary tutorial request) |
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
| `GET` | `/render/{id}/preview` | HTML preview |
| `GET` | `/export/{id}/download` | Download zip bundle |
| `GET` | `/export/{id}/pdf` | Download PDF |
| `GET` | `/export/{id}/docx` | Download Word document |

---

## Database Migrations

Append-only migration runner in `artifacts/api-server/storage/migrations.py`. Migrations run automatically at startup.

---

## PDF Export

HTML output is print-ready — open in a browser and use **File → Print → Save as PDF**. Server-side PDF is available via Playwright at `/api/export/{id}/pdf`.
