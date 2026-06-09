# Tutorial Builder — Test Prompt

Use this payload to test the coding-tutorial pivot end-to-end.

## API payload

```json
{
  "title": "Next.js SaaS Landing Page — Beginner Walkthrough",
  "lifeEvent": "Build a SaaS landing page with Next.js and Tailwind",
  "audience": "beginner",
  "tone": "project-based",
  "formattingProfile": "hands-on build",
  "artifactDensity": "standard",
  "context": "Stack / language / framework: Next.js 14, TypeScript, Tailwind CSS\nPlatform / environment: Vercel deployment, local dev with pnpm\nInclude code snippets: yes\nConstraints: No paid UI kits; keep dependencies minimal; target under 3 hours"
}
```

## Expected pipeline behavior

1. **Tutorial Framing** — names the project, lists modules (scaffold, layout, sections, deploy), defines checkpoints.
2. **Tutorial Outline** — module titles like "Scaffold App Router Project" with code exercises per module.
3. **Step Detail Mapping** — walkthrough narrative with commands, file paths, and verification steps.
4. **Implementation Examples** — fill-in worksheets and code reference tables.
5. **Reference & Troubleshooting** — Next.js/Tailwind glossary, common build errors.
6. **Delivery Layout / Render Blueprint** — structured HTML tutorial document.
7. **Validation Audit** — checks prerequisites and step dependencies.

## Quick curl

```bash
curl -X POST http://localhost:8080/api/projects \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "title": "Next.js SaaS Landing Page — Beginner Walkthrough",
  "lifeEvent": "Build a SaaS landing page with Next.js and Tailwind",
  "audience": "beginner",
  "tone": "project-based",
  "formattingProfile": "hands-on build",
  "artifactDensity": "standard",
  "context": "Stack: Next.js 14, TypeScript, Tailwind. Platform: Vercel. Include code snippets: yes"
}
EOF
```
