# Life System Builder

Converts life events — estate administration, caregiving, divorce, disability, disaster recovery — into structured operational control systems with a full LLM pipeline, Pydantic schema validation, and print-ready HTML document rendering.

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

## Five-Stage LLM Pipeline

Each stage consumes the outputs of all previous stages as structured context.

| # | Stage | Purpose |
|---|-------|---------|
| 1 | **System Architecture** | Maps the life event into domains, roles, and structural framework |
| 2 | **Worksheet System** | Generates task worksheets, trackers, and checklists per domain |
| 3 | **Layout Mapping** | Assigns document archetypes and page layout structures |
| 4 | **Render Blueprint** | Produces the final page manifest with content and formatting |
| 5 | **Validation Audit** | Compiler-style consistency checks (no LLM — pure structural) |

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


## Proposed v2 architecture

A redesign proposal focused on reducing pipeline complexity, adding a dedicated research stage, and making PDF generation deterministic is documented in `docs/architecture-v2-proposal.md`.

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

---

## API Reference

All routes are prefixed with `/api`.

### Projects
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects` | List all projects |
| `POST` | `/projects` | Create a project |
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

Server-side PDF rendering is not yet implemented. The HTML output is fully print-ready — open it in any browser and use **File → Print → Save as PDF**. The export zip bundle includes `pdf/PENDING.txt` with instructions.

When implementing PDF in the future, the correct hook is `ExportService.export_pdf()` in `services/export_service.py`, which currently raises `NotImplementedError`. Recommended approach: headless Chrome via Playwright.
