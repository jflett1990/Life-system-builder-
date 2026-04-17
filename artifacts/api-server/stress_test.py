"""
Stress-test driver for the v2 pipeline.

Boots the stack in-process (SQLite, Anthropic session token), creates a project
with a demanding multi-domain prompt, and runs:

  system_architecture → document_outline → research_graph → content_plan → voice_profile

Then prints per-stage timing, token spend, output shape, and validator results.
No FastAPI server needed — calls PipelineService directly.

Run:
  cd artifacts/api-server
  python3 stress_test.py
"""
from __future__ import annotations

import os
import sys
import time
import json

# ── Stress prompt ─────────────────────────────────────────────────────────────
# A demanding multi-domain scenario: eldercare crisis + concurrent estate
# planning + property transfer, with a blended audience.

STRESS_LIFE_EVENT = (
    "Parent diagnosed with mid-stage Alzheimer's: simultaneous Medicaid spend-down, "
    "durable power of attorney establishment, contested will, nursing home selection "
    "and contract review, Medicare Part A/B/D coordination, caregiver employment "
    "compliance, and inter-state property transfer from Florida to Texas"
)

STRESS_AUDIENCE = (
    "Adult child (45–60) with limited legal and financial literacy, acting as primary "
    "caregiver and soon-to-be legal guardian; may have siblings with conflicting interests"
)

STRESS_TONE = "clinical precision with compassionate framing"

STRESS_CONTEXT = (
    "Family has significant assets but limited cash liquidity. Parent owns a Florida "
    "homestead and a Texas investment property. Three adult children; one is estranged. "
    "Existing estate documents (will + healthcare proxy) are 20 years old and may not "
    "be valid under current law. Medicaid eligibility is borderline — spend-down may "
    "require structured spend or trust vehicle. Timeline pressure: parent may lose "
    "decision-making capacity within 6–12 months."
)


def _divider(label: str) -> None:
    print(f"\n{'═' * 70}")
    print(f"  {label}")
    print('═' * 70)


def _section(label: str) -> None:
    print(f"\n── {label} {'─' * max(0, 62 - len(label))}")


def run() -> None:
    _divider("LIFE SYSTEM BUILDER  v2  —  STRESS TEST")
    print(f"  Event : {STRESS_LIFE_EVENT[:80]}...")
    print(f"  Model : claude-sonnet-4-6 (executor) / claude-opus-4-6 (planner)")

    # ── 1. Init DB ────────────────────────────────────────────────────────────
    _section("Initialising database")
    os.environ["DATABASE_URL"] = "sqlite:///./stress_test.db"
    resume = os.path.exists("stress_test.db")

    from storage.database import init_db, SessionLocal
    init_db()
    print("  SQLite DB ready.")

    from core.contract_registry import validate_and_load
    validate_and_load()
    print("  Contract registry loaded.")

    # ── 2. Create project ─────────────────────────────────────────────────────
    _section("Creating project")
    db = SessionLocal()
    from services.project_service import ProjectService
    from schemas.project import ProjectCreate
    psvc = ProjectService(db)
    if resume:
        project = psvc.get(1)
        print(f"  Resumed project_id={project.id}")
    else:
        project = psvc.create(ProjectCreate(
            title="Alzheimer's Family System — Stress Test",
            life_event=STRESS_LIFE_EVENT,
            audience=STRESS_AUDIENCE,
            tone=STRESS_TONE,
            context=STRESS_CONTEXT,
        ))
    print(f"  project_id={project.id}  life_event={project.life_event[:60]}...")

    # ── 3. Run stages ─────────────────────────────────────────────────────────
    from services.pipeline_service import PipelineService
    from core.budget_controller import project_spend_summary

    pipeline = PipelineService(db)

    STAGES = [
        "system_architecture",
        "document_outline",
        "research_graph",
        "content_plan",
        "voice_profile",
    ]

    results: dict[str, dict] = {}

    for stage in STAGES:
        _divider(f"STAGE: {stage.upper()}")
        t0 = time.time()
        row = pipeline.run_stage(project.id, stage, force=True)
        elapsed = time.time() - t0

        output = row.get_output() if row.json_output else {}
        validation = row.get_validation() if row.validation_result else {}
        preview = row.preview_text or ""

        results[stage] = {
            "status": row.status,
            "elapsed_s": round(elapsed, 1),
            "preview": preview,
            "output_keys": list(output.keys()) if output else [],
            "error": row.error_message,
        }

        print(f"  Status  : {row.status}")
        print(f"  Elapsed : {elapsed:.1f}s")
        print(f"  Preview : {preview[:120]}")
        if output:
            print(f"  Keys    : {list(output.keys())}")
            _print_output_summary(stage, output)
        if validation:
            print(f"  Validation:")
            _print_validation(validation)
        if row.error_message:
            print(f"  ERROR: {row.error_message[:300]}")

        if row.status in ("failed", "schema_failed"):
            print(f"\n  ⚠  Stage failed — stopping pipeline.")
            break

    # ── 4. Spend summary ──────────────────────────────────────────────────────
    _divider("SPEND TELEMETRY")
    summary = project_spend_summary(project.id)
    print(f"  Total tokens  : {summary['total_tokens']:,}")
    print(f"  Premium tokens: {summary['premium_tokens']:,}")
    print(f"  Mid tokens    : {summary['mid_tokens']:,}")
    print(f"  Small tokens  : {summary['small_tokens']:,}")
    print(f"  Retry events  : {summary['retry_count']}")
    print(f"  Stages billed : {list(summary['per_stage'].keys())}")

    # ── 5. Pipeline progress ──────────────────────────────────────────────────
    _divider("PIPELINE PROGRESS")
    from core.pipeline_orchestrator import PipelineOrchestrator
    completed = pipeline.completed_stages(project.id)
    progress = PipelineOrchestrator().pipeline_progress(completed)
    print(f"  Completed : {progress['completed']}/{progress['total']} v1 stages")
    print(f"  Remaining : {progress['remaining']}")
    print(f"  Next      : {progress['next']}")

    # ── 6. Delta scope preview ────────────────────────────────────────────────
    _divider("DELTA SCOPE  (if system_architecture were edited)")
    scope = PipelineOrchestrator().delta_scope("system_architecture")
    print(f"  Edited     : {scope['edited']}")
    print(f"  Invalidated: {scope['invalidated']}")
    print(f"  Rerun order: {scope['rerun_order']}")

    # ── 7. v2 validator results ───────────────────────────────────────────────
    _divider("SUMMARY")
    for stage, info in results.items():
        tick = "✓" if info["status"] == "complete" else "✗"
        print(f"  {tick} {stage:<30} {info['elapsed_s']:5.1f}s  [{info['status']}]")

    db.close()
    if os.path.exists("stress_test.db"):
        os.remove("stress_test.db")
    print()


def _print_output_summary(stage: str, output: dict) -> None:
    if stage == "system_architecture":
        domains = output.get("control_domains", [])
        print(f"  Domains : {len(domains)}")
        for d in domains[:5]:
            print(f"    • {d.get('name', '?')}")

    elif stage == "document_outline":
        chapters = output.get("chapters", [])
        print(f"  Chapters: {len(chapters)}")
        for ch in chapters[:6]:
            print(f"    [{ch.get('chapter_number','?')}] {ch.get('title', ch.get('domain_name','?'))}")

    elif stage == "research_graph":
        facts = output.get("facts", [])
        coverage = output.get("event_coverage", {})
        print(f"  Facts   : {len(facts)}")
        print(f"  Coverage: {coverage}")
        for f in facts[:4]:
            print(f"    [{f.get('fact_id','?')}] {str(f.get('claim',''))[:80]}")

    elif stage == "content_plan":
        chapter_map = output.get("chapter_map", {})
        if isinstance(chapter_map, dict):
            items = list(chapter_map.items())[:3]
            print(f"  Chapters: {len(chapter_map)}")
            for cid, plan in items:
                print(f"    ch{cid}: depth_weight={plan.get('depth_weight','?')}  "
                      f"target_words={plan.get('target_words','?')}")
        elif isinstance(chapter_map, list):
            print(f"  Chapters: {len(chapter_map)}")
            for item in chapter_map[:3]:
                if isinstance(item, dict):
                    print(f"    ch{item.get('chapter_id', item.get('id','?'))}: "
                          f"depth_weight={item.get('depth_weight','?')}  "
                          f"target_words={item.get('target_words','?')}")

    elif stage == "voice_profile":
        constraints = output.get("lexical_constraints", [])
        banned = output.get("generic_phrase_blocklist", [])
        print(f"  Constraints: {len(constraints)}")
        print(f"  Banned phrases: {len(banned)}")
        for c in constraints[:4]:
            print(f"    [{c.get('constraint_type','?')}] {c.get('value','?')[:60]}")


def _print_validation(v: dict) -> None:
    for key, val in v.items():
        if isinstance(val, dict):
            passed = val.get("passed", "?")
            print(f"    {key}: passed={passed}")
        else:
            print(f"    {key}: {str(val)[:80]}")


if __name__ == "__main__":
    run()
