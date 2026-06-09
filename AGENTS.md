# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

**Life System Builder** is a pnpm monorepo with a React + Vite frontend (`artifacts/life-system-builder`) and a Python FastAPI backend (`artifacts/api-server`). The frontend proxies `/api/*` to the backend on port 8080.

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
| `pnpm run typecheck` | Root typecheck; may fail on duplicate exports in `lib/api-zod` (known issue) |
| `pnpm exec prettier --check "artifacts/**/*.{ts,tsx}" "lib/**/*.{ts,tsx}"` | Format check only; many files may not match Prettier defaults |
| `cd artifacts/api-server && python3 -m pytest tests/ -v` | Backend unit tests (58+ pass; 2 theme-token template tests may fail) |

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
