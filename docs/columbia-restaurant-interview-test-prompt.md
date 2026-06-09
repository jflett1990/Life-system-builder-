# Chrome Extension Tab Manager — Tutorial Builder Test Prompt

Use this prompt to test whether the pipeline can produce a specific, non-generic, coding-first project walkthrough.

## Core prompt

```text
Build a Chrome extension for tab management using Manifest V3.

Build me a project walkthrough that includes:
- Manifest V3 concepts and required files.
- A popup UI that lists open tabs.
- Actions to group, close, and pin tabs.
- Minimal permissions with clear explanations.
- A service worker explanation.
- Local loading instructions in Chrome.
- Debugging notes for permissions, service worker reloads, and popup state.
- Suggested improvements such as search, saved sessions, and keyboard shortcuts.

Context and constraints:
- Audience is beginner-to-intermediate JavaScript developers.
- Keep dependencies minimal.
- Include code snippets.
- Use checklist-driven checkpoints after every major step.

Output goal:
Produce a print-ready project tutorial with setup, implementation steps, code examples, checkpoints, common mistakes, final outcome, and next extensions.
```

## API test payload (example)

```json
{
  "title": "Chrome Extension Tab Manager Walkthrough",
  "lifeEvent": "Build a Chrome extension for tab management using Manifest V3.",
  "audience": "beginner-to-intermediate",
  "tone": "checklist-driven",
  "context": "Language / framework / stack: vanilla JavaScript, HTML, CSS, Chrome Extensions Manifest V3. Platform / environment: Chrome local extension loading. Include code snippets: yes. Constraints: minimal dependencies, smallest reasonable permissions, explain service worker reload/debug flow.",
  "formattingProfile": "hands-on build",
  "artifactDensity": "detailed + code snippets"
}
```

## Evaluation checklist for this scenario

Use this checklist to verify output quality:

- Explains Manifest V3 files and extension lifecycle.
- Includes concrete `manifest.json`, popup, and service worker examples.
- Describes permissions and why each permission is needed.
- Provides local Chrome loading and reload/debug steps.
- Includes verification checkpoints after each feature.
- Avoids generic web-app advice that ignores Chrome extension constraints.

## Expected pass signal

A strong run should read like a project tutorial a learner can follow to build, load, test, debug, and extend the extension.
