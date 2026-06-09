# Tutorial Builder

Tutorial Builder is a monorepo app that turns a tutorial request into a structured walkthrough with a staged pipeline, validation, and polished export output. The default UX is optimized for coding and vibe-coding use cases: build guides, debugging walkthroughs, architecture explainers, and deploy playbooks.

---

## Product Overview

Users provide a tutorial prompt (for example, "Build a CRUD app with Supabase"), plus optional structure controls (skill level, tutorial type, depth, output style, constraints). The system then generates a tutorial artifact with practical sections such as:

- Goal and target learner
- Prerequisites and setup tools
- Step-by-step implementation flow
- Code snippets and verification checkpoints
- Common mistakes and debugging notes
- Final outcome and next improvements

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ artifacts/life-system-builder  (React + Vite frontend)          │
│ - pages/components/hooks for tutorial intake + results          │
│ - Vite proxies /api/* to backend on :8080                       │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│ artifacts/api-server  (FastAPI backend)                         │
│ - api/routes: projects, pipeline, render, export, validation    │
│ - services: project, pipeline, render, validation, export       │
│ - contracts/v1: staged prompt contracts for tutorial generation  │
│ - render/: manifest + templates + HTML/DOCX export builders     │
└───────────────────────────┬──────────────────────────────────────┘
                            │ SQLAlchemy
┌───────────────────────────▼──────────────────────────────────────┐
│ DB (SQLite/Postgres): projects, stage outputs, renders,         │
│ validation reports, migrations                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tutorial Pipeline (Conceptual 5 Stages)

The implementation reuses the existing staged architecture and maps it to tutorial semantics:

1. **Tutorial Framing**  
   Interpret request, learner fit, scope, prerequisites, constraints.
2. **Tutorial Outline**  
   Create modules/steps, milestones, and flow order.
3. **Tutorial Detail Mapping**  
   Expand modules with implementation details, examples, checkpoints.
4. **Render Blueprint / Delivery Format**  
   Produce structured manifest and layout guidance for rendering.
5. **Validation Audit**  
   Run structural and consistency checks across stage outputs.

Notes:
- Internal stage IDs remain stable for compatibility with persistence and APIs.
- Persistence strategy is unchanged; semantic output is pivoted to tutorial content.

---

## Run Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm 9+

### Backend (FastAPI)

```bash
cd artifacts/api-server
export PATH="$HOME/.local/bin:$PATH"
export DATABASE_URL=sqlite:///./life_system.db PORT=8080
python3 main.py
```

Health check:

```bash
curl http://localhost:8080/api/healthz
```

Expected:

```text
{"status":"ok","db":"ready"}
```

### Frontend (React + Vite)

From repo root:

```bash
export PORT=25676 BASE_PATH=/
pnpm --filter @workspace/life-system-builder run dev
```

---

## Testing and Validation

Useful repo commands:

```bash
pnpm run typecheck
cd artifacts/api-server && python3 -m pytest tests/ -v
```

Known notes in this repo:
- Root typecheck may report known generated-export duplication in `lib/api-zod`.
- Backend tests are high signal for pipeline/render/export changes.

---

## Primary Use Cases

- Build a full-stack project tutorial from scratch
- Generate a deployment checklist and walkthrough
- Turn a debugging scenario into a stepwise resolution guide
- Produce architecture walkthroughs with implementation checkpoints
- Create concise or detailed project-based coding lessons

---

## API Surface (High Level)

All routes are under `/api`:

- `projects`: create/update/list tutorial projects
- `pipeline`: run per-stage or full generation + validation
- `render`: produce HTML preview/manifest output
- `export`: download tutorial HTML/DOCX/JSON bundles

---

## LLM Provider Notes

Full pipeline generation requires one configured provider:

- `ANTHROPIC_API_KEY`, or
- `AI_INTEGRATIONS_OPENAI_API_KEY` plus `AI_INTEGRATIONS_OPENAI_BASE_URL`

CRUD, routing, and much of UI behavior can still be exercised without keys.

