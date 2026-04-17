"""
Unit tests for the v2 rewrite modules (Phases A–C).

Covers:
  - HeightEstimator  (geometry-first rendering math)
  - GenericityGuard  (voice compliance / per-project banned phrase memory)
  - WorksheetTransformer (deterministic worksheet generation)
  - Research graph builder (fact retrieval + confidence scoring)
  - PipelineOrchestrator delta_scope (downstream invalidation)
  - BudgetController model tier routing

Run with:
  cd artifacts/api-server && python -m pytest tests/test_v2_pipeline.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── HeightEstimator ──────────────────────────────────────────────────────────

class TestHeightEstimator:
    def _estimator(self):
        from render.height_estimator import HeightEstimator
        return HeightEstimator()

    def test_heading_heights_are_fixed(self):
        from render.height_estimator import BlockType
        est = self._estimator()
        assert est.estimate(BlockType.H1).estimated_px == 72
        assert est.estimate(BlockType.H2).estimated_px == 56
        assert est.estimate(BlockType.H3).estimated_px == 44

    def test_paragraph_scales_with_length(self):
        from render.height_estimator import BlockType
        est = self._estimator()
        short = est.estimate(BlockType.PARAGRAPH, char_count=40).estimated_px
        long_ = est.estimate(BlockType.PARAGRAPH, char_count=4000).estimated_px
        assert long_ > short

    def test_table_row_scales_with_count(self):
        from render.height_estimator import BlockType
        est = self._estimator()
        two_row = est.estimate(BlockType.TABLE_DATA_ROW, row_count=2).estimated_px
        ten_row = est.estimate(BlockType.TABLE_DATA_ROW, row_count=10).estimated_px
        assert ten_row > two_row

    def test_full_page_types_return_effective_zone(self):
        from render.height_estimator import BlockType, EFFECTIVE_ZONE_PX
        est = self._estimator()
        cover = est.estimate(BlockType.COVER_PAGE)
        divider = est.estimate(BlockType.SECTION_DIVIDER)
        assert cover.is_full_page
        assert divider.is_full_page
        assert cover.estimated_px == EFFECTIVE_ZONE_PX

    def test_string_alias_accepts_block_type_value(self):
        est = self._estimator()
        assert est.estimate("h1").estimated_px == 72


# ── WorksheetTransformer ─────────────────────────────────────────────────────

class TestWorksheetTransformer:
    def _seed(self, seed_id: str, ws_type: str, title: str) -> dict:
        return {
            "seed_id": seed_id,
            "worksheet_type": ws_type,
            "domain_id": "eldercare",
            "title": title,
        }

    def test_task_tracker_columns(self):
        from authoring.worksheet_transformer import WorksheetTransformer
        seeds = [self._seed("ws-1", "task_tracker", "Probate Task Tracker")]
        packets = WorksheetTransformer().transform(seeds)
        assert len(packets) == 1
        column_names = [c.name for c in packets[0].columns]
        assert "Task" in column_names
        assert len(packets[0].columns) >= 4

    def test_contact_sheet_structure(self):
        from authoring.worksheet_transformer import WorksheetTransformer
        seeds = [self._seed("ws-2", "contact_sheet", "Eldercare Contacts")]
        brief = {"key_entities": []}
        packets = WorksheetTransformer().transform(seeds, brief=brief)
        column_names = [c.name for c in packets[0].columns]
        assert "Phone" in column_names
        assert "Email" in column_names

    def test_unknown_type_falls_back_gracefully(self):
        from authoring.worksheet_transformer import WorksheetTransformer
        seeds = [self._seed("ws-unknown", "nonexistent_type", "Mystery")]
        packets = WorksheetTransformer().transform(seeds)
        assert len(packets) == 1
        assert len(packets[0].columns) >= 1


# ── GenericityGuard ─────────────────────────────────────────────────────────

class TestGenericityGuard:
    def test_flags_global_banned_phrase(self):
        from authoring.genericity_guard import GenericityGuard
        guard = GenericityGuard(project_id=1001, voice_profile={})
        result = guard.check("It's important to note that paperwork matters.")
        assert not result.passed
        assert len(result.violations) >= 1

    def test_clean_text_passes(self):
        from authoring.genericity_guard import GenericityGuard
        guard = GenericityGuard(project_id=1002, voice_profile={})
        result = guard.check(
            "File Form SSA-721 within 60 days of the death to start the survivor claim."
        )
        assert result.passed

    def test_project_banned_phrases_accumulate(self):
        from authoring.genericity_guard import (
            GenericityGuard,
            record_rejected_phrases,
            get_project_banned_phrases,
        )
        record_rejected_phrases(project_id=2001, phrases=["vague filler noun"])
        banned = get_project_banned_phrases(project_id=2001)
        assert "vague filler noun" in banned


# ── PipelineOrchestrator delta_scope ────────────────────────────────────────

class TestDeltaScope:
    def test_editing_early_stage_invalidates_all_downstream(self):
        from core.pipeline_orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        scope = orch.delta_scope("document_outline")
        # chapter_expansion and all later v1 stages must be in the invalidation set
        assert "chapter_expansion" in scope["invalidated"]
        assert "render_blueprint" in scope["invalidated"]
        assert "validation_audit" in scope["invalidated"]

    def test_editing_leaf_stage_invalidates_nothing(self):
        from core.pipeline_orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        scope = orch.delta_scope("validation_audit")
        assert scope["invalidated"] == []

    def test_rerun_order_is_canonical(self):
        from core.pipeline_orchestrator import PipelineOrchestrator
        from schemas.stage import ALL_STAGE_NAMES
        orch = PipelineOrchestrator()
        scope = orch.delta_scope("system_architecture")
        # rerun_order must preserve ALL_STAGE_NAMES ordering
        canonical_index = {s: i for i, s in enumerate(ALL_STAGE_NAMES)}
        indices = [canonical_index[s] for s in scope["rerun_order"]]
        assert indices == sorted(indices)


# ── BudgetController ────────────────────────────────────────────────────────

class TestBudgetController:
    def test_premium_tier_only_for_prose(self):
        from core.budget_controller import STAGE_ROUTING, ModelTier
        assert STAGE_ROUTING["chapter_prose"] == ModelTier.PREMIUM
        assert STAGE_ROUTING["chapter_expansion"] == ModelTier.PREMIUM
        # Planning stages must not be premium
        assert STAGE_ROUTING["content_plan"] != ModelTier.PREMIUM
        assert STAGE_ROUTING["research_graph"] != ModelTier.PREMIUM

    def test_deterministic_stages_have_zero_budget(self):
        from core.budget_controller import STAGE_BUDGETS
        assert STAGE_BUDGETS["worksheet_transform"].input_tokens == 0
        assert STAGE_BUDGETS["manifest_build"].output_tokens == 0
        assert STAGE_BUDGETS["render"].input_tokens == 0

    def test_record_spend_appends_to_project_registry(self):
        from core.budget_controller import (
            BudgetController,
            clear_project_spend,
            project_spend_summary,
        )
        clear_project_spend(9999)
        bc = BudgetController(project_id=9999)
        bc.record_spend("research_graph", "gpt-4o", input_tokens=100, output_tokens=50)
        bc.record_spend("chapter_prose", "claude-opus", input_tokens=1200, output_tokens=600)
        summary = project_spend_summary(9999)
        assert summary["event_count"] == 2
        assert summary["total_tokens"] == 100 + 50 + 1200 + 600
        assert "research_graph" in summary["per_stage"]
        assert "chapter_prose" in summary["per_stage"]
        clear_project_spend(9999)


# ── ArtifactRegistry ────────────────────────────────────────────────────────

class TestArtifactRegistry:
    def test_write_and_latest_round_trip(self):
        from core.artifact_registry import ArtifactRegistry
        reg = ArtifactRegistry()
        rev = reg.write(
            project_id=42,
            stage="research_graph",
            model_id="gpt-4o",
            contract_version="v1",
            schema_version="1.0",
            payload={"facts": []},
        )
        assert rev.revision_id
        latest = reg.latest(
            project_id=42,
            stage="research_graph",
            model_id="gpt-4o",
            contract_version="v1",
        )
        assert latest is not None
        assert latest.payload == {"facts": []}

    def test_content_addressed_revision_id_is_stable(self):
        from core.artifact_registry import ArtifactRegistry
        reg = ArtifactRegistry()
        r1 = reg.write(
            project_id=43,
            stage="content_plan",
            model_id="gpt-4o",
            contract_version="v1",
            schema_version="1.0",
            payload={"chapter_map": {"1": {"words": 3000}}},
        )
        r2 = reg.write(
            project_id=43,
            stage="content_plan",
            model_id="gpt-4o",
            contract_version="v1",
            schema_version="1.0",
            payload={"chapter_map": {"1": {"words": 3000}}},
        )
        # Same payload → same revision_id (content-addressed)
        assert r1.revision_id == r2.revision_id
        # Cache hit for the key
        assert reg.hit(
            project_id=43,
            stage="content_plan",
            model_id="gpt-4o",
            contract_version="v1",
        )


# ── ResearchIntegrityValidator ──────────────────────────────────────────────

class TestResearchIntegrity:
    def test_chapter_with_no_citations_fails(self):
        from validators.research_integrity import ResearchIntegrityValidator
        graph = {"facts": []}
        validator = ResearchIntegrityValidator(research_graph=graph)
        packet = {
            "chapter_id": "1",
            "blocks": [
                {"block_id": "b1", "block_type": "narrative", "content": "Some text", "fact_ids": []},
            ],
        }
        result = validator.validate_chapter(packet)
        assert not result.passed
        assert any(v.violation_type == "missing_citation" for v in result.violations)

    def test_chapter_with_valid_citations_passes(self):
        from validators.research_integrity import ResearchIntegrityValidator
        graph = {"facts": [{"fact_id": "F-1", "claim": "Test fact"}]}
        validator = ResearchIntegrityValidator(research_graph=graph)
        packet = {
            "chapter_id": "1",
            "blocks": [
                {"block_id": "b1", "block_type": "narrative", "content": "Text", "fact_ids": ["F-1"]},
            ],
        }
        result = validator.validate_chapter(packet)
        assert result.citation_coverage == 1.0
