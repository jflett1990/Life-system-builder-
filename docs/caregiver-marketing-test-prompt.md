# Streaming AI Chat App — Tutorial Builder Test Prompt

Use this prompt when creating a Tutorial Builder project for a coding-heavy, hands-on build walkthrough.

## Core prompt

```text
Show me how to build an AI chat app with streaming responses using FastAPI, React, and Server-Sent Events.

Tutorial goals:
- Explain the end-to-end architecture before coding.
- Build a FastAPI streaming endpoint.
- Build a React chat UI that renders streamed tokens incrementally.
- Include environment variable setup, local run commands, and basic tests.
- Show how to debug common streaming failures.

Structured context to include:
- Beginner-to-intermediate audience.
- Local development on macOS or Linux.
- Prefer minimal dependencies.
- Include code snippets.
- Use verification checkpoints after backend, frontend, integration, and deployment readiness steps.

Constraints:
- Avoid using a full auth system.
- Keep the first version deployable later but local-first.
- Explain where an OpenAI-compatible provider or mock streaming adapter would plug in.

Audience and tone:
- Primary: vibe coders and junior full-stack developers.
- Tone: project-based, practical, and debugging-friendly.

Output goal:
Produce a polished tutorial with prerequisites, setup, step-by-step implementation, code examples, checkpoints, common mistakes, final outcome, and next improvements.
```

## API test payload (example)

```json
{
  "title": "Streaming AI Chat App Walkthrough",
  "lifeEvent": "Show me how to build an AI chat app with streaming responses using FastAPI, React, and Server-Sent Events.",
  "audience": "intermediate",
  "tone": "project-based",
  "context": "Language / framework / stack: FastAPI, React, Server-Sent Events. Platform / environment: local macOS or Linux dev environment. Include code snippets: yes. Constraints: no auth in v1, minimal dependencies, local-first, explain where an OpenAI-compatible provider or mock streaming adapter plugs in.",
  "formattingProfile": "hands-on build",
  "artifactDensity": "detailed + code snippets"
}
```

## Observed test-run status in this environment

- Project creation should succeed.
- Stage `system_architecture` should frame a tutorial, not a life-event system.
- The rendered output should include prerequisites, tools/setup, implementation steps, checkpoints, debugging notes, final outcome, and next improvements.
