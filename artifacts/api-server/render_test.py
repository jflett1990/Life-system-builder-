"""
End-to-end PDF render test for the v2 pipeline.

Uses a focused 2-domain life event to minimise LLM call count, runs all
required stages, then renders to PDF via Playwright and saves output.

Run:
  cd artifacts/api-server
  python3 render_test.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

# ── Test prompt ───────────────────────────────────────────────────────────────
# Deliberately narrow: probate only, single US state, no contested elements.
# Produces a 2-domain outline so chapter_expansion runs just 4 LLM calls.

LIFE_EVENT = (
    "Probating a deceased parent's estate in California: validating and filing the will, "
    "appointing an executor, inventorying and appraising assets, notifying creditors, "
    "settling debts and taxes, and distributing the remaining estate to three adult heirs"
)

AUDIENCE = "Adult child (35–55) named as executor, no prior probate experience"
TONE = "direct and precise"
CONTEXT = (
    "Estate includes a primary residence, two bank accounts, a brokerage account, "
    "and personal property. No real estate outside California. Total gross estate "
    "approximately $850k. Will is current and uncontested. One heir lives abroad."
)

OUTPUT_PDF = "/tmp/life_system_render_test.pdf"
OUTPUT_HTML = "/tmp/life_system_render_test.html"


def _divider(label: str) -> None:
    print(f"\n{'═' * 68}")
    print(f"  {label}")
    print('═' * 68)


def _section(label: str) -> None:
    print(f"\n── {label} {'─' * max(0, 60 - len(label))}")


def run() -> None:
    _divider("LIFE SYSTEM BUILDER  v2  —  RENDER TEST")
    print(f"  Event: {LIFE_EVENT[:80]}...")

    # ── DB + registry ──────────────────────────────────────────────────────────
    _section("Init")
    os.environ["DATABASE_URL"] = "sqlite:///./render_test.db"
    if os.path.exists("render_test.db"):
        os.remove("render_test.db")

    from storage.database import init_db, SessionLocal
    init_db()
    from core.contract_registry import validate_and_load
    validate_and_load()
    print("  DB + contracts ready.")

    # ── Project ────────────────────────────────────────────────────────────────
    db = SessionLocal()
    from services.project_service import ProjectService
    from schemas.project import ProjectCreate
    project = ProjectService(db).create(ProjectCreate(
        title="California Probate Executor Guide — Render Test",
        life_event=LIFE_EVENT,
        audience=AUDIENCE,
        tone=TONE,
        context=CONTEXT,
    ))
    print(f"  project_id={project.id}")

    # ── Pipeline stages ────────────────────────────────────────────────────────
    from services.pipeline_service import PipelineService
    pipeline = PipelineService(db)

    STAGES = [
        "system_architecture",
        "document_outline",
        "chapter_expansion",
        "chapter_worksheets",
        "appendix_builder",
        "layout_mapping",
        "render_blueprint",
    ]

    # Stages that are allowed to fail without halting the render
    SOFT_STAGES = {"chapter_worksheets", "appendix_builder"}

    timings: dict[str, float] = {}

    for stage in STAGES:
        _divider(f"STAGE: {stage.upper()}")

        # Cool down before worksheet stage to avoid hitting rate limits
        # immediately after the heavy chapter_expansion parallel burst
        if stage == "chapter_worksheets":
            print("  [cooldown 90s to clear rate-limit window]")
            time.sleep(90)

        t0 = time.time()
        row = pipeline.run_stage(project.id, stage, force=True)
        elapsed = time.time() - t0
        timings[stage] = elapsed

        output = row.get_output() if row.json_output else {}
        print(f"  Status : {row.status}")
        print(f"  Time   : {elapsed:.1f}s")
        print(f"  Preview: {(row.preview_text or '')[:120]}")
        if row.error_message:
            print(f"  ERROR  : {row.error_message[:200]}")

        if row.status in ("failed", "schema_failed"):
            if stage in SOFT_STAGES:
                print(f"  [non-fatal — continuing to render without {stage}]")
                continue
            print("\n  Pipeline halted — cannot render.")
            _cleanup(db)
            return

        # Show chapter count for chapter_expansion
        if stage == "chapter_expansion" and output:
            chapters = output.get("chapters", [])
            print(f"  Chapters generated: {len(chapters)}")
            for ch in chapters[:6]:
                words = len((ch.get("narrative", "") or "").split())
                print(f"    [{ch.get('chapter_number','?')}] {ch.get('domain_name','?')[:55]}  ~{words:,}w")

    # ── Render HTML ────────────────────────────────────────────────────────────
    _divider("RENDER: HTML")
    from services.render_service import RenderService
    render_svc = RenderService(db)

    t0 = time.time()
    result = render_svc.render(project.id)
    html_elapsed = time.time() - t0
    print(f"  Pages  : {result.page_count}")
    print(f"  Time   : {html_elapsed:.1f}s")
    print(f"  HTML   : {len(result.html):,} bytes")

    with open(OUTPUT_HTML, "w") as f:
        f.write(result.html)
    print(f"  Saved  : {OUTPUT_HTML}")

    # ── Render PDF ─────────────────────────────────────────────────────────────
    _divider("RENDER: PDF")
    t0 = time.time()
    try:
        from services.export_service import ExportService
        export_svc = ExportService(db)
        pdf_bytes = export_svc.export_pdf(project.id)
        pdf_elapsed = time.time() - t0
        with open(OUTPUT_PDF, "wb") as f:
            f.write(pdf_bytes)
        print(f"  Size   : {len(pdf_bytes):,} bytes  ({len(pdf_bytes) // 1024} KB)")
        print(f"  Time   : {pdf_elapsed:.1f}s")
        print(f"  Saved  : {OUTPUT_PDF}")
    except Exception as e:
        print(f"  PDF render error: {e}")

    # ── Summary ────────────────────────────────────────────────────────────────
    _divider("SUMMARY")
    for s, t in timings.items():
        tick = "✓"
        print(f"  {tick} {s:<30} {t:6.1f}s")
    print(f"  {'render (HTML)':<30} {html_elapsed:6.1f}s")
    total = sum(timings.values()) + html_elapsed
    print(f"\n  Total wall time: {total:.0f}s  ({total/60:.1f} min)")
    print(f"  HTML: {OUTPUT_HTML}")
    print(f"  PDF:  {OUTPUT_PDF}")

    _cleanup(db)


def _cleanup(db) -> None:
    db.close()
    if os.path.exists("render_test.db"):
        os.remove("render_test.db")


if __name__ == "__main__":
    run()
