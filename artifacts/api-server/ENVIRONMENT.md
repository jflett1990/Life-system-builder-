# Environment Setup

## Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string. Falls back to `sqlite:///./life_system.db` if unset. |
| `AI_INTEGRATIONS_OPENAI_API_KEY` | Yes | OpenAI API key for LLM pipeline stages. |
| `AI_INTEGRATIONS_OPENAI_BASE_URL` | Yes | OpenAI API base URL. Use `https://api.openai.com/v1` for standard OpenAI, or a Replit AI Integrations proxy URL. |

## Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_MODEL` | `gpt-5.2` | Model to use for pipeline stages. |
| `PORT` | `8080` | Port for the FastAPI server. |
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

## Replit Setup

On Replit, set secrets via the Secrets panel (never commit keys to source control):

```
AI_INTEGRATIONS_OPENAI_API_KEY   → your OpenAI key
AI_INTEGRATIONS_OPENAI_BASE_URL  → https://api.openai.com/v1
SESSION_SECRET                   → random 32-character string
```

`DATABASE_URL` is provided automatically by Replit PostgreSQL.

## Local Development

For local development without PostgreSQL, use SQLite:

```bash
export DATABASE_URL="sqlite:///./life_system.db"
export AI_INTEGRATIONS_OPENAI_API_KEY="sk-..."
export AI_INTEGRATIONS_OPENAI_BASE_URL="https://api.openai.com/v1"
```

SQLite is fully supported — the migration runner detects the dialect automatically.

## Model Configuration

The default model is `gpt-5.2`. To override per-session:

```bash
export OPENAI_MODEL="gpt-4o"
```

The `ModelService` in `models_integration/model_service.py` reads this at import time.
Changing the model mid-session has no effect on already-running requests.

## Database Migrations

Migrations run automatically at startup. No manual steps required.
If a migration fails, the server will log the error and exit. Check the log for the migration number and function name.

To inspect applied migrations:

```sql
SELECT version, name, applied_at FROM schema_migrations ORDER BY version;
```

## Health Check

```bash
curl http://localhost:8080/api/health
# → {"status": "ok", "version": "..."}
```
