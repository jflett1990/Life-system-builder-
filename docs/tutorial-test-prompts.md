# Tutorial Builder — Test Prompts

Sample tutorial requests for exercising the pipeline. Each block maps to the
intake fields on the New Tutorial form (`POST /api/projects`).

## 1. Hands-on web build (beginner)

```text
Topic:        Build a SaaS landing page with Next.js and Tailwind
Skill level:  beginner
Type:         hands-on build
Stack:        Next.js 14, Tailwind CSS, TypeScript
Platform:     macOS, Node 20, Vercel
Depth:        standard
Include code: yes
Output style: project-based
Constraints:  one weekend; free-tier services only; no Docker
Context:      Knows basic HTML/CSS, has never used a React framework.
```

## 2. Bot build (intermediate)

```text
Topic:        Create a Discord bot with Python that moderates spam and supports slash commands
Skill level:  intermediate
Type:         hands-on build
Stack:        Python 3.11, discord.py
Platform:     Linux VPS or free hosting
Depth:        standard
Include code: yes
Output style: checklist-driven
Constraints:  must run 24/7 on a free or cheap host
```

## 3. CRUD app (beginner → intermediate)

```text
Topic:        Build a CRUD app with Supabase — tasks list with auth and row-level security
Skill level:  beginner
Type:         hands-on build
Stack:        React, Vite, Supabase (Postgres + Auth)
Depth:        deep-dive
Include code: yes
Output style: project-based
Constraints:  avoid paid tiers; explain RLS policies carefully
```

## 4. Deployment walkthrough

```text
Topic:        Walk me through deploying a FastAPI app to production
Skill level:  intermediate
Type:         deployment guide
Stack:        FastAPI, uvicorn, Docker, Fly.io or Railway
Depth:        standard
Include code: yes
Output style: checklist-driven
Constraints:  zero-downtime deploys preferred; budget under $10/month
```

## 5. Browser extension

```text
Topic:        Build a Chrome extension for tab management (group, suspend, and search tabs)
Skill level:  intermediate
Type:         hands-on build
Stack:        JavaScript, Chrome Extension Manifest V3
Depth:        standard
Include code: yes
Output style: project-based
```

## 6. AI app with streaming (advanced)

```text
Topic:        Show me how to make an AI chat app with streaming responses
Skill level:  advanced
Type:         architecture walkthrough
Stack:        Next.js, Vercel AI SDK or raw SSE, OpenAI-compatible API
Depth:        deep-dive
Include code: yes
Output style: detailed
Constraints:  must handle proxy buffering, token-by-token rendering, and abort/retry
```

## 7. Non-coding sanity check

The builder should remain usable for any topic — defaults just bias toward coding.

```text
Topic:        Teach me how to plan and cook a week of meals in one Sunday session
Skill level:  beginner
Type:         overview
Depth:        quick
Include code: no
Output style: checklist-driven
```
