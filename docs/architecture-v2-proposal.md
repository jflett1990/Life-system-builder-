# Life System Builder — Architecture v2 Proposal

## Why this redesign

Current pain points are real and recurring:

1. **Pipeline feels bloated**: too many generation stages, too many cross-stage dependencies, and unclear ownership boundaries.
2. **PDF output is brittle**: content generation and page geometry decisions are mixed, so formatting problems are hard to isolate.
3. **Output sounds templated/generic**: prompts optimize for schema completion more than source-grounded specificity.
4. **Missing explicit research step**: domain facts are generated without a dedicated evidence model.

This proposal reduces orchestration complexity, introduces a research-first content strategy, and makes PDF production deterministic.

---

## Design principles

- **Separation of concerns**: facts, prose, and layout should be independent artifacts.
- **Deterministic rendering**: no model call during HTML/PDF rendering.
- **Composable stages**: each stage has one narrow responsibility and a strict input/output contract.
- **Human-auditable provenance**: every major claim in generated content should map back to research evidence.
- **Opinionated but flexible style system**: templates control structure, while a style profile controls brand voice and specificity.

---

## Proposed v2 pipeline (6 stages)

### Stage 0 — Intake Normalization (new)
**Goal**: normalize user inputs into a canonical project brief.

**Input**
- user intake fields
- audience + constraints
- locale/jurisdiction hints

**Output**
- `project_brief.json`
- normalized entities (people, places, deadlines, systems)
- unresolved questions list

---

### Stage 1 — Research Graph (new)
**Goal**: build a structured evidence pack before any long-form writing.

**Input**
- `project_brief.json`

**Output**
- `research_graph.json` with:
  - facts
  - citations/sources
  - confidence score per fact
  - jurisdiction tags
  - conflict flags (fact disagreements)

**Notes**
- This can combine retrieval + model extraction, but the stored output is a deterministic JSON graph.
- If confidence is below threshold, pipeline pauses with explicit follow-up questions.

---

### Stage 2 — Strategy Blueprint (replaces multiple upstream planning stages)
**Goal**: convert evidence into a domain strategy model.

**Input**
- `project_brief.json`
- `research_graph.json`

**Output**
- `strategy_blueprint.json`
  - domains
  - goals
  - operating principles
  - role responsibilities
  - milestones and risk gates

---

### Stage 3 — Content Plan + Voice Profile (new anti-generic layer)
**Goal**: define what to write and how it should sound before chapter generation.

**Input**
- `strategy_blueprint.json`
- optional user brand kit / writing samples

**Output**
- `content_plan.json` (chapter map, component choices, depth targets)
- `voice_profile.json`:
  - lexical constraints
  - banned generic phrases
  - required domain terminology
  - audience reading level and tone controls

---

### Stage 4 — Chapter Composer (merged generation)
**Goal**: produce structured chapter content with citation anchors.

**Input**
- `content_plan.json`
- `voice_profile.json`
- `research_graph.json`

**Output**
- `chapter_packets/*.json`
  - chapter body blocks
  - worksheet blocks
  - source anchors (`fact_id` references)
  - rewrite rationale metadata

**Quality gates**
- reject if citation coverage < target
- reject if generic-language detector triggers
- reject if required entities from brief are missing

---

### Stage 5 — Render Spec + Deterministic Typesetting (reworked PDF path)
**Goal**: convert chapter packets to a strict document manifest and render identically to HTML and PDF.

**Input**
- `chapter_packets`
- design tokens + page spec

**Output**
- `document_manifest.json` (single source of truth for layout)
- `rendered.html`
- `rendered.pdf`
- `layout_report.json` (overflows, widows/orphans, page break decisions)

**Implementation rule**
- renderer never calls the model; it only maps manifest -> templates -> print engine.

---

## What changes from current architecture

### 1) Collapse and simplify generation chain
Current multi-step authoring (`document_outline`, `chapter_expansion`, `chapter_worksheets`, `appendix_builder`) becomes:
- one planning stage (`content_plan`)
- one generation stage (`chapter_composer`)

This reduces stage coupling and makes reruns cheaper.

### 2) Add explicit research state as a first-class artifact
`research_graph.json` becomes required upstream data for all claims, preventing unsupported filler text and improving specificity.

### 3) Move “voice” out of prompts and into data
A dedicated `voice_profile.json` prevents generic wording drift and enables tunable style controls without rewriting all templates/prompts.

### 4) Make PDF a strict rendering concern
Layout decisions happen in `document_manifest.json`; HTML and PDF share the same manifest to avoid output divergence.

---

## Proposed module boundaries

### `core/`
- `pipeline_orchestrator.py` (new DAG with stage contracts)
- `artifact_registry.py` (typed artifact metadata)

### `research/` (new)
- `retrieval.py`
- `fact_extractor.py`
- `graph_builder.py`
- `confidence.py`

### `authoring/` (new)
- `strategy_builder.py`
- `content_planner.py`
- `voice_profiler.py`
- `chapter_composer.py`
- `genericity_guard.py`

### `render/`
- `manifest_builder.py` (strict mapping from packets to pages)
- `html_renderer.py`
- `pdf_renderer.py` (Playwright/Chromium)
- `layout_analyzer.py`

### `validators/`
- `research_integrity.py`
- `citation_coverage.py`
- `voice_compliance.py`
- `layout_safety.py`

---

## Data contracts (new canonical artifacts)

- `project_brief.json`
- `research_graph.json`
- `strategy_blueprint.json`
- `content_plan.json`
- `voice_profile.json`
- `chapter_packets/*.json`
- `document_manifest.json`
- `layout_report.json`

Each artifact should be versioned (`schema_version`) and persisted as immutable revisions.

---

## PDF reliability strategy

1. **Single layout source**: `document_manifest.json` drives both HTML and PDF.
2. **Hard geometry checks**: pre-render validator catches overflow risks before export.
3. **Visual regression snapshots**: hash each page screenshot in CI for drift detection.
4. **Fallback rules**: if page block overflows, apply deterministic fallback (split table, continue marker, reduced heading spacing) and log it in `layout_report.json`.
5. **No hidden CSS magic**: all page-break directives generated from manifest, not ad hoc template conditionals.

---

## Anti-generic content strategy

- **Evidence-linked writing**: each paragraph references one or more `fact_id`s.
- **Lexical diversity guard**: n-gram repetition and cliché phrase detection.
- **Domain terminology quotas**: require specific, context-relevant term usage.
- **Negative prompt memory**: maintain banned phrase list from prior outputs per project.
- **Sample-conditioned tone**: optional user-provided writing sample forms part of `voice_profile`.

---


## LLM budget and token-burn control (reality-first)

If we are serious about operating cost and latency, this must be a first-class architecture concern, not a prompt tweak.

### Core budget policy

- **Per-project token envelope**: set a hard max input/output token budget per run and per stage.
- **Per-stage spend caps**: each stage gets a token + retry budget and cannot exceed it without explicit override.
- **Quality tiering**: default to lower-cost models for extraction/classification; reserve premium models for synthesis/final polish.
- **Stop-loss behavior**: once confidence is sufficient, stop generating more variants.

### High-impact cost controls

1. **Context compaction pipeline**
   - Persist compact structured artifacts between stages (`facts`, `entities`, `claims`) instead of passing raw prior prose.
   - Use deterministic summarizers to create stage-specific context packs.

2. **Model routing by task type**
   - Extraction/normalization -> small fast model.
   - Planning and structure -> mid-tier model.
   - Final narrative refinement (limited scope) -> top-tier model.

3. **Semantic cache + artifact cache**
   - Cache stage outputs keyed by `(project_revision, stage, model, contract_version)`.
   - Add near-duplicate cache hits for repeated user edits where upstream artifacts did not materially change.

4. **Delta generation instead of full regeneration**
   - If a user edits one domain/chapter, rerun only impacted packets.
   - Enforce dependency graph to avoid full pipeline reruns.

5. **Constrained generation formats**
   - Use strict JSON schemas and response-format constraints to reduce retries and repair loops.
   - Keep generation windows narrow (section-by-section), then compose deterministically.

6. **Guardrail before generation**
   - Run cheap validators first (schema completeness, required entities, missing citations).
   - Skip expensive generation when preconditions are not met.

### Operational controls

- **Real-time spend telemetry**: track tokens, latency, retries, and cache hit rates by stage.
- **Budget-aware orchestration**: orchestrator chooses cheaper fallback strategy when budget utilization is high.
- **A/B model policy**: continuously test cheaper model candidates for extraction/planning tasks.

### Suggested SLO/SLA targets

- >= 60% of runs should complete with no premium-model call before final synthesis.
- >= 40% median token reduction versus current baseline.
- >= 70% cache hit rate on iterative revisions.

---

## If doing a full overhaul rewrite: recommended architecture

If this were a true rewrite, I would recommend a **document compiler architecture** with strict intermediate representations (IRs), not a prompt-chain architecture.

### Compiler-style layers

1. **Front-end (ingest + research)**
   - Intake parser -> normalized project brief.
   - Retrieval + extraction -> research graph IR.

2. **Middle-end (planning + authoring transforms)**
   - Strategy planner IR.
   - Content plan IR.
   - Chapter packet IR with fact anchors.

3. **Back-end (layout + render targets)**
   - Document manifest IR.
   - HTML backend and PDF backend compiled from same manifest.

### Why this is better in reality

- **Predictable costs**: each compile pass has measurable token/latency budget.
- **Better debuggability**: failures are isolated to one IR transform.
- **Safer iteration**: you can recompile one pass without regenerating everything.
- **Higher output quality**: evidence anchors and voice policy become data constraints, not wishful prompt text.

### Rewrite priorities (in order)

1. Implement artifact/version registry + DAG runner with budget enforcement.
2. Introduce research graph and citation coverage validator.
3. Replace freeform chapter generation with packetized section compiler.
4. Introduce canonical document manifest and deterministic PDF backend.
5. Add telemetry dashboard (token burn, retries, cache efficiency, failure causes).

---
## Migration plan (low risk)

### Phase A — Parallel artifacts (no UI break)
- Add new artifacts (`project_brief`, `research_graph`, `voice_profile`) while preserving existing stages.
- Run new validators in warning mode.

### Phase B — Stage consolidation
- Replace `document_outline` + `chapter_expansion` + `chapter_worksheets` with `content_plan` + `chapter_composer`.
- Keep compatibility adapters for old render blueprint input.

### Phase C — Deterministic PDF path
- Introduce `document_manifest` and new `pdf_renderer`.
- Deprecate direct template decisions from blueprint JSON.

### Phase D — Cleanup
- Remove legacy stages and contracts once migration metrics are stable.

---

## Success metrics

- **Pipeline runtime**: reduce median full run time by 25%.
- **Re-run cost**: stage rerun after content edits <= 2 stages.
- **PDF failure rate**: < 2% layout validation failures.
- **Genericity score**: 40% reduction in cliché detector hits.
- **Citation coverage**: >= 85% of factual blocks linked to research facts.

---

## Immediate next implementation slice

1. Add `research_graph` stage and schema.
2. Add `voice_profile` schema + simple generic phrase validator.
3. Refactor renderer input to intermediate `document_manifest` while keeping current templates.
4. Add layout report endpoint and include it in export bundle.

This gives near-term wins (research grounding + PDF diagnostics) without requiring a full rewrite.
