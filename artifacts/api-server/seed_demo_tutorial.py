"""Dev utility: seeds a project with realistic tutorial-shaped stage outputs
so the render/export/validation paths can be exercised without LLM API keys.

The project itself must exist first (create it via the UI or POST /api/projects);
this script then fills in completed outputs for all content stages.

Run from artifacts/api-server:
  DATABASE_URL=sqlite:///./life_system.db python3 seed_demo_tutorial.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

PROJECT_ID = 1

NARRATIVE_1 = """## What You're Building
In this step you containerise the FastAPI app so it runs identically on your laptop and on Fly.io. By the end you will have a Dockerfile, a .dockerignore, and a locally running container responding on port 8080.

## Step-by-Step Implementation
1. Create a `Dockerfile` in the project root. Expected result: `docker build .` completes and prints a final image id.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

2. Add a `.dockerignore` so the image stays small. Expected result: the build context shrinks below a few MB.

```text
.venv/
__pycache__/
*.db
.git/
```

3. Build and run the container. Expected result: `curl localhost:8080/healthz` returns `{"status":"ok"}`.

```bash
docker build -t fastapi-demo .
docker run -p 8080:8080 fastapi-demo
```

## How It Works
The slim base image keeps cold-start small. Copying `requirements.txt` before the source preserves Docker layer caching, so code-only changes rebuild in seconds. Binding uvicorn to 0.0.0.0 is what makes the app reachable from outside the container.

## Common Mistakes and Debugging
If `curl` returns connection refused, the most common cause is uvicorn bound to 127.0.0.1 inside the container — check the CMD line. If the build fails with `COPY failed: file not found`, you are building from the wrong directory; run the build from the project root.

## Checkpoint and Hand-off
This step is complete when the container builds with no errors and the health endpoint answers from the mapped port. The next step deploys this exact image to Fly.io, so commit your Dockerfile before continuing.
"""

NARRATIVE_2 = """## What You're Building
In this step you ship the container to Fly.io with secrets configured and a public HTTPS URL. By the end the app is live and `fly status` shows a healthy machine.

## Step-by-Step Implementation
1. Install the CLI and authenticate. Expected result: `fly auth whoami` prints your email.

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

2. Launch the app without deploying yet, then set secrets. Expected result: `fly secrets list` shows DATABASE_URL with a digest.

```bash
fly launch --no-deploy
fly secrets set DATABASE_URL=postgres://...
```

3. Deploy and verify. Expected result: `fly status` reports one healthy machine and the URL serves the health check.

```bash
fly deploy
curl https://your-app.fly.dev/healthz
```

## How It Works
`fly launch` reads your Dockerfile and generates fly.toml with an internal_port that must match the port uvicorn binds. Secrets are injected as environment variables at boot, never baked into the image.

## Common Mistakes and Debugging
If the deploy hangs on health checks, the internal_port in fly.toml does not match 8080 — fix it and redeploy. If the app boots then crashes with a missing env var, the secret was set after the machine started; run `fly deploy` again to restart with secrets.

## Checkpoint and Hand-off
This step is complete when the public URL answers the health check over HTTPS. You now have a repeatable deploy loop: build, deploy, verify.
"""


def seed() -> None:
    from storage.database import init_db, SessionLocal
    from models.stage_output import StageOutput

    init_db()
    db = SessionLocal()

    outputs: dict[str, dict] = {
        "tutorial_research": {
            "research_summary": "FastAPI deployment via Docker and Fly.io is a stable, well-documented path. The version-sensitive areas are the Fly.io CLI (flyctl) flags and fly.toml schema, which change a few times a year. Learners most often get stuck on container port binding and on secrets being set after the first machine boots.",
            "facts": [
                {"fact_id": "fact-01", "claim": "uvicorn must bind 0.0.0.0 inside a container or the mapped port refuses connections", "category": "configuration", "applies_to_modules": ["domain-01"], "confidence": "high", "source_hint": "Uvicorn docs — Deployment"},
                {"fact_id": "fact-02", "claim": "Docker reuses cached layers per instruction; copying requirements.txt before source code makes code-only rebuilds take seconds", "category": "concept", "applies_to_modules": ["domain-01"], "confidence": "high", "source_hint": "Docker docs — Dockerfile best practices"},
                {"fact_id": "fact-03", "claim": "Fly.io health checks probe the internal_port declared in fly.toml; a mismatch with the app port hangs the deploy", "category": "gotcha", "applies_to_modules": ["domain-02"], "confidence": "high", "source_hint": "Fly.io docs — fly.toml reference"},
                {"fact_id": "fact-04", "claim": "fly secrets are injected as env vars at machine boot, not at build time", "category": "security", "applies_to_modules": ["domain-02"], "confidence": "high", "source_hint": "Fly.io docs — Secrets"},
                {"fact_id": "fact-05", "claim": "The current default machine preset for new Fly.io apps is shared-cpu-1x with 256MB", "category": "version", "applies_to_modules": ["domain-02"], "confidence": "low", "source_hint": "Fly.io docs — Machine sizing"},
            ],
            "version_baselines": [
                {"tool": "Python", "minimum_version": "3.11 — verify with `python3 --version`", "notes": "Matches the python:3.11-slim base image used in step 1"},
                {"tool": "flyctl", "minimum_version": "latest — verify with `fly version`", "notes": "fly.toml schema changes between major versions"},
            ],
            "common_errors": [
                {"symptom": "curl: (7) Failed to connect to localhost port 8080: Connection refused", "cause": "uvicorn bound to 127.0.0.1 inside the container", "fix": "Set `--host 0.0.0.0` in the Dockerfile CMD", "applies_to_modules": ["domain-01"]},
                {"symptom": "Deploy hangs at 'waiting for machine to be healthy' then rolls back", "cause": "fly.toml internal_port does not match the uvicorn port", "fix": "Set internal_port = 8080 in fly.toml", "applies_to_modules": ["domain-02"]},
                {"symptom": "Machine boots then crash-loops with KeyError on an env var", "cause": "Secrets set after the machine first started", "fix": "Run `fly deploy` again so the machine restarts with secrets", "applies_to_modules": ["domain-02"]},
            ],
            "key_commands": [
                {"command": "docker build -t fastapi-demo .", "run_from": "project root", "purpose": "Build the deployable image", "expected_output": "Final line prints the image id", "applies_to_modules": ["domain-01"]},
                {"command": "fly launch --no-deploy", "run_from": "project root", "purpose": "Generate fly.toml without deploying", "expected_output": "fly.toml written; app created", "applies_to_modules": ["domain-02"]},
                {"command": "fly secrets set DATABASE_URL=...", "run_from": "project root", "purpose": "Inject runtime secrets", "expected_output": "Secrets are staged for the next deploy", "applies_to_modules": ["domain-02"]},
            ],
            "reference_links": [
                {"title": "FastAPI docs — Deployment", "url": "https://fastapi.tiangolo.com/deployment/", "why": "Canonical deployment concepts and ASGI server options"},
                {"title": "Fly.io docs — fly.toml reference", "url": "https://fly.io/docs/reference/configuration/", "why": "internal_port and health check configuration"},
            ],
            "open_questions": [
                "Verify the current default machine preset with `fly platform vm-sizes` before writing step 2 (fact-05 is low confidence)",
            ],
        },
        "system_architecture": {
            "system_name": "Deploy a FastAPI App to Production with Docker and Fly.io",
            "topic": "Walk me through deploying a FastAPI app",
            "operating_premise": "Deploying FastAPI involves a dozen small configuration decisions — ports, secrets, health checks — and getting any one wrong produces a deploy that hangs or an app that crashes on boot with no obvious error.",
            "system_objective": "Finish with the app live at a public HTTPS URL: `curl https://your-app.fly.dev/healthz` returns {\"status\":\"ok\"} and `fly status` shows a healthy machine.",
            "time_horizon": "2-3 hours hands-on, including account setup",
            "control_domains": [
                {"id": "domain-01", "name": "Containerising the FastAPI App with Docker", "purpose": "Produce a small, cache-friendly image that runs identically everywhere", "scope_in": ["Dockerfile", ".dockerignore", "local container smoke test"], "scope_out": ["Kubernetes manifests — out of scope for a single-app deploy"], "primary_outputs": ["Dockerfile", "working local container on port 8080"]},
                {"id": "domain-02", "name": "Fly.io Launch, Secrets, and First Deploy", "purpose": "Ship the image with secrets configured and verify a healthy public URL", "scope_in": ["fly launch", "fly secrets", "fly deploy", "smoke test"], "scope_out": ["Custom domains and TLS certificates — see next steps"], "primary_outputs": ["fly.toml", "live HTTPS URL", "healthy machine in fly status"]},
            ],
            "key_roles": [
                {"role": "FastAPI + uvicorn", "responsibility": "The app server — must bind 0.0.0.0:8080 inside the container", "authority_level": "required"},
                {"role": "Docker", "responsibility": "Builds the deployable image with layer caching", "authority_level": "required"},
                {"role": "Fly.io (flyctl)", "responsibility": "Hosts the container, injects secrets, terminates TLS", "authority_level": "required"},
            ],
            "critical_milestones": [
                {"milestone": "Container answers locally", "description": "`curl localhost:8080/healthz` returns ok from the running container", "sequence": 1},
                {"milestone": "First deploy healthy", "description": "`fly status` shows a started machine passing checks", "sequence": 2},
            ],
            "success_criteria": [
                "`docker build .` completes with zero errors",
                "`curl localhost:8080/healthz` returns {\"status\":\"ok\"} from the container",
                "`fly deploy` finishes with a healthy machine and the public URL serves the health check",
            ],
            "failure_modes": [
                "uvicorn bound to 127.0.0.1 inside the container — connection refused on the mapped port",
                "fly.toml internal_port mismatch with the uvicorn port — deploy hangs on health checks",
                "Secrets set after machine start — app crashes on boot with missing env vars until redeployed",
            ],
            "operating_constraints": [
                "Docker Desktop or docker engine installed and running",
                "Free Fly.io account with payment method verified",
                "Budget under $10/month — single shared-cpu machine",
            ],
        },
        "document_outline": {
            "document_title": "Deploy a FastAPI App to Production with Docker and Fly.io",
            "document_subtitle": "A hands-on deployment walkthrough for developers shipping their first production API",
            "system_name": "Deploy a FastAPI App to Production with Docker and Fly.io",
            "version": "1.0",
            "total_chapters": 2,
            "master_operating_rules": [
                "Commit after every passing checkpoint — Rationale: each step builds on the last and a known-good commit is the fastest rollback. Trigger: every time a checkpoint checklist fully passes. Risk: a broken change in step 2 forces re-doing step 1 by hand instead of `git checkout`.",
                "Never bake secrets into the image — Rationale: images are pushed to registries and cached on build hosts. Trigger: any time a value would go into the Dockerfile ENV. Risk: leaked DATABASE_URL requires credential rotation and a full redeploy.",
            ],
            "cascade_chain": [
                {"source_domain": "Containerising the FastAPI App with Docker", "triggers": ["Fly.io Launch, Secrets, and First Deploy"], "condition": "When the local container passes its smoke test, the same image config is consumed by fly launch"},
            ],
            "disclaimer_required": False,
            "introduction_text": "This walkthrough takes a working FastAPI app from your laptop to a public HTTPS URL on Fly.io. You will containerise the app with Docker, configure secrets safely, and ship a verified first deploy with a repeatable loop.",
            "chapters": [
                {"chapter_number": 1, "domain_id": "domain-01", "domain_name": "Containerising the FastAPI App with Docker", "chapter_title": "Containerise the FastAPI App with a Cache-Friendly Dockerfile", "chapter_purpose": "After this step you can build and run the app as a container that answers on port 8080.", "key_topics": ["Dockerfile layer ordering for fast rebuilds", "Binding uvicorn to 0.0.0.0", ".dockerignore and build context size"], "common_gap": "Binding uvicorn to 127.0.0.1 inside the container — everything builds, but the mapped port refuses connections.", "cascade_triggers": ["When the local smoke test passes, fly launch can reuse the Dockerfile unchanged"], "worksheet_plan": [{"worksheet_id": "ws-01-a", "title": "Local Container Smoke Test Checklist", "purpose": "Verify the image builds and answers before any cloud setup", "section_count": 1, "estimated_field_count": 8}, {"worksheet_id": "ws-01-b", "title": "Docker Command Reference", "purpose": "The exact build/run/debug commands with expected outputs", "section_count": 1, "estimated_field_count": 10}]},
                {"chapter_number": 2, "domain_id": "domain-02", "domain_name": "Fly.io Launch, Secrets, and First Deploy", "chapter_title": "Launch on Fly.io with Secrets and a Verified First Deploy", "chapter_purpose": "After this step the app is live at a public HTTPS URL with secrets injected at boot.", "key_topics": ["fly launch and fly.toml internal_port", "fly secrets vs build-time env", "Reading deploy health checks"], "common_gap": "internal_port in fly.toml not matching the uvicorn port, so the deploy hangs on health checks.", "cascade_triggers": [], "worksheet_plan": [{"worksheet_id": "ws-02-a", "title": "Pre-Deploy Configuration Record", "purpose": "Record app name, region, ports, and secrets before deploying", "section_count": 2, "estimated_field_count": 8}]},
            ],
        },
        "chapter_expansion": {
            "chapters": [
                {
                    "chapter_number": 1,
                    "domain_id": "domain-01",
                    "chapter_title": "Containerise the FastAPI App with a Cache-Friendly Dockerfile",
                    "narrative": NARRATIVE_1,
                    "chapter_opener": {
                        "what_this_is_for": "Build a Docker image of the FastAPI app that runs identically on your laptop and in production.",
                        "when_it_matters": "First step — the deploy in step 2 ships this exact image.",
                        "failure_looks_like": "`curl localhost:8080/healthz` returns connection refused even though the container is running.",
                        "produces": ["Dockerfile", ".dockerignore", "local container answering on port 8080"],
                        "do_first": ["Create the Dockerfile in the project root", "Run `docker build -t fastapi-demo .`"],
                    },
                    "minimum_viable_actions": ["Write the 6-line Dockerfile", "Add .dockerignore", "docker build -t fastapi-demo .", "docker run -p 8080:8080 fastapi-demo", "curl localhost:8080/healthz"],
                    "quick_reference_rules": [
                        "Copy requirements.txt before source code — Rationale: preserves layer caching. Trigger: every Dockerfile edit. Risk: full dependency reinstall on every code change, minutes per rebuild.",
                        "Bind uvicorn to 0.0.0.0 — Rationale: 127.0.0.1 is unreachable from outside the container. Trigger: writing the CMD line. Risk: connection refused on the mapped port.",
                    ],
                    "decision_guide": [
                        {"decision": "Base image choice", "if_condition": "You need system packages (psycopg2, lxml)", "then_action": "Use python:3.11-slim and apt-get the build deps", "else_action": "Stay on python:3.11-slim as-is", "escalate_when": "Image exceeds 1 GB — switch to a multi-stage build"},
                        {"decision": "Port configuration", "if_condition": "The platform injects $PORT", "then_action": "Read the port from the environment in CMD", "else_action": "Hardcode 8080 and map it", "escalate_when": "Health checks fail after both options — inspect `docker logs`"},
                        {"decision": "Dependency pinning", "if_condition": "requirements.txt has unpinned versions", "then_action": "Pin with `pip freeze > requirements.txt` before building", "else_action": "Proceed", "escalate_when": "Build works locally but fails in CI with resolver errors"},
                    ],
                    "trigger_blocks": ["If the build fails with 'COPY failed: file not found', you are building from the wrong directory — run from the project root.", "If the container exits immediately, run `docker logs <id>` and check for a missing module — usually a file excluded by .dockerignore."],
                    "risk_blocks": ["A bloated build context (venv, .git) slows every build — verify with the 'Sending build context' size line.", "Installing dev dependencies in the image inflates cold starts — keep requirements.txt production-only."],
                    "output_summaries": ["Dockerfile — consumed unchanged by fly launch in step 2", "Verified local container — proves the app config before touching the cloud"],
                    "worksheet_linkage": [{"worksheet_title": "Local Container Smoke Test Checklist", "use_when": "Right after `docker run`", "unblocks": "Moving to the Fly.io launch in step 2"}],
                    "cascade_triggers": ["When the smoke test checklist passes, step 2's `fly launch` can begin"],
                    "scenario_scene": "Maya builds the image, runs it, and gets connection refused on port 8080. She checks the CMD line, spots `--host 127.0.0.1`, changes it to 0.0.0.0, rebuilds in 4 seconds thanks to layer caching, and the health check answers.",
                    "success_metrics": ["`docker build` completes in under 2 minutes on first build", "Rebuild after a code-only change takes under 10 seconds", "`curl localhost:8080/healthz` returns {\"status\":\"ok\"}"],
                    "detailed_explanation": "Docker builds the image as a stack of layers, one per instruction. Because layers are content-addressed, putting the rarely-changing dependency install before the frequently-changing source copy means most rebuilds reuse the expensive layer. The .dockerignore matters twice: it shrinks the context upload and prevents secrets or local databases from leaking into image layers.",
                },
                {
                    "chapter_number": 2,
                    "domain_id": "domain-02",
                    "chapter_title": "Launch on Fly.io with Secrets and a Verified First Deploy",
                    "narrative": NARRATIVE_2,
                    "chapter_opener": {
                        "what_this_is_for": "Ship the container to Fly.io with secrets injected at boot and verify a healthy public URL.",
                        "when_it_matters": "After the local container passes its smoke test in step 1.",
                        "failure_looks_like": "`fly deploy` hangs on health checks, or the machine boots and crashes with a missing env var.",
                        "produces": ["fly.toml", "configured secrets", "live HTTPS URL"],
                        "do_first": ["Run `fly launch --no-deploy`", "Set secrets with `fly secrets set`"],
                    },
                    "minimum_viable_actions": ["fly auth login", "fly launch --no-deploy", "fly secrets set DATABASE_URL=...", "fly deploy", "curl https://your-app.fly.dev/healthz"],
                    "quick_reference_rules": [
                        "Set secrets before the first deploy — Rationale: machines read env at boot. Trigger: immediately after fly launch. Risk: a crash-looping machine that needs another deploy to fix.",
                        "Match internal_port to the uvicorn port — Rationale: health checks probe internal_port. Trigger: reviewing the generated fly.toml. Risk: deploy hangs for 5 minutes then rolls back.",
                    ],
                    "decision_guide": [
                        {"decision": "Region selection", "if_condition": "Your users are mostly in Europe", "then_action": "Pick ams or fra at launch", "else_action": "Accept the suggested nearest region", "escalate_when": "p95 latency stays above 300ms — add a second region"},
                        {"decision": "Machine size", "if_condition": "Budget is under $10/month", "then_action": "Keep the default shared-cpu-1x 256MB", "else_action": "Scale with `fly scale vm`", "escalate_when": "OOM kills appear in `fly logs`"},
                        {"decision": "Database location", "if_condition": "You already have a managed Postgres", "then_action": "Point DATABASE_URL at it via secrets", "else_action": "Provision with `fly postgres create`", "escalate_when": "Connection timeouts — check private networking config"},
                    ],
                    "trigger_blocks": ["If the deploy hangs on health checks, open fly.toml and verify internal_port = 8080.", "If the machine crash-loops with a missing env var, run `fly secrets list` to confirm, then `fly deploy` to restart with secrets."],
                    "risk_blocks": ["Secrets passed as build args leak into image history — always use fly secrets.", "Skipping the post-deploy smoke test hides a broken release until users hit it."],
                    "output_summaries": ["fly.toml — the deploy contract for every future release", "Live HTTPS URL — the verifiable end state of this tutorial"],
                    "worksheet_linkage": [{"worksheet_title": "Pre-Deploy Configuration Record", "use_when": "Right before running `fly deploy`", "unblocks": "A deploy you can repeat and debug from a written record"}],
                    "cascade_triggers": [],
                    "scenario_scene": "Sam deploys and the release hangs at 'waiting for machine to be healthy'. The configuration record shows uvicorn on 8080 but fly.toml says internal_port = 3000 — a leftover from the launch scaffold. One edit and a redeploy later, the machine reports healthy in 40 seconds.",
                    "success_metrics": ["`fly deploy` completes with a healthy machine on the first attempt after config fixes", "`curl https://your-app.fly.dev/healthz` returns ok over HTTPS", "`fly secrets list` shows all required secrets before deploy"],
                    "detailed_explanation": "fly launch inspects the Dockerfile and writes fly.toml, the single source of truth for ports, health checks, and machine sizing. Secrets live outside the image and are injected as env vars when a machine boots, which is why setting them before the first deploy avoids a crash-loop. The deploy itself is immutable: every release builds a fresh machine and only switches traffic after health checks pass.",
                },
            ]
        },
        "chapter_worksheets": {
            "chapters": [
                {
                    "chapter_number": 1,
                    "domain_id": "domain-01",
                    "chapter_title": "Containerise the FastAPI App with a Cache-Friendly Dockerfile",
                    "worksheets": [
                        {
                            "id": "ws-01-a",
                            "title": "Local Container Smoke Test Checklist",
                            "layout": "checklist",
                            "purpose": "Verify the image builds and the container answers before any cloud setup.",
                            "estimated_completion_time": "10 minutes on first run, 2 minutes on re-checks",
                            "common_errors": ["Running the build from the parent folder instead of the project root, which fails the COPY step", "Testing against a stale container from an earlier build — always `docker ps` first"],
                            "checklist_items": [
                                "Run `docker build -t fastapi-demo .` from the project root — pass = final line prints the image id; fail = note the first failing instruction and fix that line before continuing.",
                                "Check the 'Sending build context' size in the build output — pass = under 10 MB; fail = add the offending directory (.venv, .git) to .dockerignore.",
                                "Run `docker run -p 8080:8080 fastapi-demo` — pass = uvicorn startup banner appears with 0.0.0.0:8080; fail = check the CMD host/port flags.",
                                "Run `curl localhost:8080/healthz` from a second terminal — pass = {\"status\":\"ok\"}; fail = connection refused means the host binding is 127.0.0.1.",
                                "Stop the container and re-run `docker build` after touching only a .py file — pass = build finishes in under 10 seconds using cached layers; fail = requirements.txt is copied after the source.",
                            ],
                            "example_items": ["✓ `docker build -t fastapi-demo .` completed — image id sha256:91f2…, total time 1m44s"],
                            "repeat_use": True,
                            "cross_references": [],
                            "decision_gates": [{"gate_id": "g-01", "gate_title": "Container answers locally", "condition": "Health check returns ok from the mapped port", "pass_action": "Proceed to Fly.io launch (step 2)", "fail_action": "Debug the CMD host binding before any cloud setup", "blocks_completion": True}],
                        },
                        {
                            "id": "ws-01-b",
                            "title": "Docker Command Reference",
                            "layout": "table",
                            "purpose": "The exact build/run/debug commands for this step with expected outputs.",
                            "estimated_completion_time": "Reference — no completion time",
                            "common_errors": ["Confusing image name and container id in debug commands", "Forgetting -p so the port is never mapped"],
                            "table_columns": ["Command (run from project root)", "What it does", "Expected output", "First debugging move if it fails"],
                            "table_row_count": 8,
                            "sample_rows": [
                                {"Command (run from project root)": "docker build -t fastapi-demo .", "What it does": "Builds the image from the Dockerfile", "Expected output": "Final line with image id", "First debugging move if it fails": "Read the first failing instruction number"},
                                {"Command (run from project root)": "docker run -p 8080:8080 fastapi-demo", "What it does": "Starts the container with the port mapped", "Expected output": "Uvicorn banner on 0.0.0.0:8080", "First debugging move if it fails": "docker logs <container id>"},
                                {"Command (run from project root)": "curl localhost:8080/healthz", "What it does": "Smoke-tests the running container", "Expected output": "{\"status\":\"ok\"}", "First debugging move if it fails": "Check CMD binds 0.0.0.0, not 127.0.0.1"},
                            ],
                            "repeat_use": True,
                            "cross_references": ["Local Container Smoke Test Checklist"],
                            "decision_gates": [],
                        },
                    ],
                },
                {
                    "chapter_number": 2,
                    "domain_id": "domain-02",
                    "chapter_title": "Launch on Fly.io with Secrets and a Verified First Deploy",
                    "worksheets": [
                        {
                            "id": "ws-02-a",
                            "title": "Pre-Deploy Configuration Record",
                            "layout": "form",
                            "purpose": "Record app name, region, ports, and secrets so the deploy is repeatable and debuggable.",
                            "estimated_completion_time": "10 minutes before first deploy, 3 minutes on updates",
                            "common_errors": ["Recording the uvicorn port but not checking fly.toml internal_port matches it", "Listing a secret as 'set' from memory instead of from `fly secrets list` output"],
                            "sections": [
                                {
                                    "section_id": "s-01",
                                    "section_title": "App Identity and Region",
                                    "instructions": "Have the output of `fly launch --no-deploy` open before completing this section. Copy values exactly as printed, not from memory. This section is complete when the app name resolves with `fly status -a <name>`.",
                                    "fields": [
                                        {"field_id": "f-001", "label": "Fly app name (from fly.toml `app =`)", "type": "text", "placeholder": "fastapi-demo-prod", "required": True, "validation_hint": "Must match `fly status` output exactly"},
                                        {"field_id": "f-002", "label": "Primary region code chosen at launch", "type": "text", "placeholder": "ams", "required": True, "validation_hint": "Three-letter Fly region code"},
                                        {"field_id": "f-003", "label": "internal_port in fly.toml (must equal uvicorn port)", "type": "number", "placeholder": "8080", "required": True, "validation_hint": "8080 — mismatches hang the deploy on health checks"},
                                    ],
                                },
                                {
                                    "section_id": "s-02",
                                    "section_title": "Secrets Verification",
                                    "instructions": "Run `fly secrets list` and copy the digest column for each secret. Do not mark a secret as set unless it appears in that output. This section is complete when every required secret has a digest recorded.",
                                    "fields": [
                                        {"field_id": "f-004", "label": "DATABASE_URL secret digest (from `fly secrets list`)", "type": "text", "placeholder": "b1946ac9…", "required": True, "validation_hint": "Digest string, never the actual URL"},
                                        {"field_id": "f-005", "label": "Deploy verified with public health check?", "type": "boolean", "placeholder": "yes", "required": True, "validation_hint": "Only after `curl https://<app>.fly.dev/healthz` returns ok"},
                                    ],
                                },
                            ],
                            "repeat_use": False,
                            "cross_references": ["Local Container Smoke Test Checklist"],
                            "decision_gates": [{"gate_id": "g-02", "gate_title": "Ports aligned", "condition": "internal_port equals the uvicorn port from step 1", "pass_action": "Run fly deploy", "fail_action": "Edit fly.toml before deploying", "blocks_completion": True}],
                        },
                    ],
                },
            ]
        },
        "appendix_builder": {
            "topic": "Walk me through deploying a FastAPI app",
            "glossary_terms": [
                {"term": ".dockerignore", "definition": "File listing paths excluded from the Docker build context — keeps images small and prevents leaking local files; used in step 1."},
                {"term": "ASGI", "definition": "The async server interface FastAPI speaks; uvicorn is the ASGI server that actually listens on the port."},
                {"term": "Build context", "definition": "Everything Docker uploads before building — the 'Sending build context' line in step 1's checklist."},
                {"term": "fly.toml", "definition": "Fly.io's per-app deploy contract: ports, health checks, machine sizing. Generated by `fly launch` in step 2."},
                {"term": "Health check", "definition": "The probe Fly.io runs against internal_port before routing traffic; a mismatch is why deploys hang."},
                {"term": "internal_port", "definition": "The container port Fly.io probes and routes to — must equal the uvicorn port (8080 in this tutorial)."},
                {"term": "Layer caching", "definition": "Docker reuses unchanged instruction layers; ordering requirements.txt before source code makes rebuilds take seconds."},
                {"term": "Secrets", "definition": "Environment values injected at machine boot via `fly secrets set` — never baked into the image."},
                {"term": "Smoke test", "definition": "The minimal end-to-end check (curl the health endpoint) run after every build and deploy."},
                {"term": "uvicorn", "definition": "The ASGI server running FastAPI; its --host flag is the root cause of most 'connection refused' failures."},
            ],
            "professional_triggers": [
                {"situation": "The build passes locally but `fly deploy` fails in the remote builder with a dependency resolver error", "professional_type": "Pin versions with `pip freeze`, then check the Fly.io community forum 'deploys' category", "urgency": "soon"},
                {"situation": "The machine boots, then crash-loops with no readable error in `fly logs`", "professional_type": "Fly.io docs — Troubleshooting → 'My app isn't working', with `fly logs` output attached", "urgency": "immediate"},
                {"situation": "Health checks pass but the public URL intermittently times out", "professional_type": "Fly.io status page first, then the community forum with `fly checks list` output", "urgency": "soon"},
                {"situation": "You are about to store real user credentials or payment data", "professional_type": "A security engineer review before going live — secrets handling and TLS configuration", "urgency": "planned"},
                {"situation": "Docker build times exceed 10 minutes despite caching", "professional_type": "Docker docs — 'Building best practices' (multi-stage builds section)", "urgency": "planned"},
            ],
            "key_resources": [
                {"organization": "FastAPI Official Documentation", "service": "Deployment guide and ASGI server options", "phone": "", "website": "https://fastapi.tiangolo.com/deployment/", "hours": ""},
                {"organization": "Fly.io Documentation", "service": "fly.toml reference, secrets, health checks", "phone": "", "website": "https://fly.io/docs/", "hours": ""},
                {"organization": "Docker Documentation", "service": "Dockerfile best practices and layer caching", "phone": "", "website": "https://docs.docker.com/", "hours": ""},
                {"organization": "Fly.io Community Forum", "service": "Deploy debugging with maintainer responses", "phone": "", "website": "https://community.fly.io/", "hours": ""},
            ],
            "include_notes_pages": True,
            "notes_page_count": 2,
        },
        "layout_mapping": {
            "document_title": "Deploy a FastAPI App to Production with Docker and Fly.io",
            "document_subtitle": "Tutorial Walkthrough — deploying a FastAPI app",
            "version": "1.0",
            "total_sections": 4,
            "print_structure": {"page_size": "Letter", "orientation": "portrait", "columns": 1, "include_toc": True, "include_index": False},
            "sections": [
                {"section_id": "sec-01", "sequence": 1, "title": "Cover", "section_type": "cover", "page_type": "full-page", "source": {"type": "architecture", "reference_id": None}, "content_slots": [{"slot_id": "slot-01", "slot_type": "heading", "source_field": "system_name", "label": "Tutorial Title", "required": True}], "cross_references": []},
                {"section_id": "sec-02", "sequence": 2, "title": "Containerise the FastAPI App", "section_type": "domain-overview", "page_type": "full-page", "source": {"type": "architecture", "reference_id": "domain-01"}, "content_slots": [{"slot_id": "slot-02", "slot_type": "body-text", "source_field": "chapters[0].narrative", "label": "Step Walkthrough", "required": True}], "cross_references": ["sec-03"]},
                {"section_id": "sec-03", "sequence": 3, "title": "Launch on Fly.io", "section_type": "domain-overview", "page_type": "full-page", "source": {"type": "architecture", "reference_id": "domain-02"}, "content_slots": [{"slot_id": "slot-03", "slot_type": "body-text", "source_field": "chapters[1].narrative", "label": "Step Walkthrough", "required": True}], "cross_references": []},
                {"section_id": "sec-04", "sequence": 4, "title": "Appendix", "section_type": "appendix", "page_type": "reference-table", "source": {"type": "generated", "reference_id": None}, "content_slots": [{"slot_id": "slot-04", "slot_type": "criteria-list", "source_field": "glossary_terms", "label": "Glossary", "required": True}], "cross_references": []},
            ],
            "navigation_map": [{"from_section": "sec-02", "to_section": "sec-03", "relationship": "precedes"}],
        },
        "render_blueprint": {
            "blueprint_name": "FastAPI Deploy Tutorial Render Blueprint",
            "theme": {
                "color_palette": {"primary": "#1e2d40", "secondary": "#2d4a6b", "accent": "#c9a84c", "background": "#fdfcfa", "surface": "#f5f2ec", "text_primary": "#1a1a1a", "text_secondary": "#5a5650", "border": "#d8d2c6"},
                "typography": {"heading_font": "Georgia", "body_font": "Arial", "mono_font": "Courier New", "base_size_px": 14, "line_height": 1.6},
                "spacing": {"page_margin_mm": 20, "section_gap_px": 48, "field_gap_px": 16},
            },
            "render_directives": [{"directive_id": "rd-01", "section_id": "sec-01", "sequence": 1, "template": "cover", "page_break_before": True, "slots": []}],
            "page_count_estimate": 14,
            "render_notes": ["DevOps palette: deep slate + gold"],
        },
    }

    for stage_name, data in outputs.items():
        row = (
            db.query(StageOutput)
            .filter(StageOutput.project_id == PROJECT_ID, StageOutput.stage_name == stage_name)
            .first()
        )
        if not row:
            row = StageOutput(project_id=PROJECT_ID, stage_name=stage_name)
            db.add(row)
        row.status = "complete"
        row.json_output = json.dumps(data)
        row.preview_text = f"Seeded demo output for {stage_name}"
        db.commit()
        print(f"seeded {stage_name}")

    db.close()
    print("done")


if __name__ == "__main__":
    seed()
