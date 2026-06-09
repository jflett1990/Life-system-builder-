# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

**Tutorial Builder** (formerly Life System Builder) is a pnpm monorepo with a React + Vite frontend (`artifacts/life-system-builder` — directory name kept from the previous incarnation) and a Python FastAPI backend (`artifacts/api-server`). It converts tutorial requests (e.g. "Build a CRUD app with Supabase") into structured step-by-step tutorials. The frontend proxies `/api/*` to the backend on port 8080. The primary project intake field is `topic` (formerly `life_event`).

### Starting services (manual)

Run these in separate tmux sessions or terminals:

**API server** (from `artifacts/api-server`):

```bash
export PATH="$HOME/.local/bin:$PATH"
export DATABASE_URL=sqlite:///./life_system.db PORT=8080
python3 main.py
```

Use `python3`, not `python` — only `python3` is on PATH in this VM.

**Frontend** (from repo root):

```bash
export PORT=25676 BASE_PATH=/
pnpm --filter @workspace/life-system-builder run dev
```

Both `PORT` and `BASE_PATH` are required by `vite.config.ts`.

Health check: `curl http://localhost:8080/api/healthz` → `{"status":"ok","db":"ready"}`

### Lint / test / typecheck

| Command | Notes |
|---------|-------|
| `pnpm run typecheck` | Root typecheck (libs + artifacts); should pass clean |
| `pnpm exec prettier --check "artifacts/**/*.{ts,tsx}" "lib/**/*.{ts,tsx}"` | Format check only; many files may not match Prettier defaults |
| `cd artifacts/api-server && python3 -m pytest tests/ -v` | Backend unit tests (70+; should pass clean) |
| `pnpm --filter @workspace/api-spec run codegen` | Regenerate orval clients after editing `lib/api-spec/openapi.yaml` |

There is no ESLint config or frontend test suite in this repo.

### LLM pipeline

Full pipeline runs require `ANTHROPIC_API_KEY` or `AI_INTEGRATIONS_OPENAI_API_KEY` + `AI_INTEGRATIONS_OPENAI_BASE_URL`. Default provider is Anthropic (`model_provider: anthropic` in `core/config.py`). CRUD and UI work without API keys.

### Optional services

- **Mockup sandbox**: `PORT=8081 BASE_PATH=/__mockup pnpm --filter @workspace/mockup-sandbox run dev`
- **Legacy Node API** (`artifacts/api-server/src/`): do not run alongside the Python API (same port 8080).

### Gotchas

- API startup may run `playwright install chromium` if no system Chromium is found; this is non-blocking.
- DB migrations run automatically at API startup in a background thread; mutations return 503 until DB is ready.
- `pip install` puts scripts in `~/.local/bin` — add to PATH before running `uvicorn`, `pytest`, or `playwright`.
