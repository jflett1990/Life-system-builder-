"""
Tests for the tutorial-builder pivot:
  - contract registry loads all tutorial contracts
  - every pipeline stage resolves to a registered contract
  - prompt assembly works end-to-end with the tutorial payload
  - tutorial narrative heading checks accept the new structure
  - ProjectCreate accepts the tutorial intake fields (camelCase + snake_case)

Run with:
  cd artifacts/api-server && python3 -m pytest tests/test_tutorial_contracts.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SAMPLE_PAYLOAD = {
    "topic": "Build a SaaS landing page with Next.js and Tailwind",
    "audience": "self-directed learners and developers",
    "tone": "clear, practical, encouraging",
    "context": "",
    "skill_level": "beginner",
    "tutorial_type": "hands-on build",
    "stack": "Next.js 14, Tailwind CSS",
    "platform": "macOS",
    "depth": "standard",
    "include_code": "yes",
    "output_style": "project-based",
    "constraints": "no Docker",
}


@pytest.fixture(scope="module")
def registry():
    from core.contract_registry import validate_and_load
    return validate_and_load()


class TestContractRegistry:
    def test_loads_all_contracts(self, registry) -> None:
        names = {c.name for c in registry.list_all()}
        assert "tutorial_orchestrator" in names
        assert "tutorial_framing_core" in names
        assert "tutorial_validation_agent" in names
        assert "life_system_orchestrator" not in names
        assert "life_event_system_core" not in names

    def test_every_v1_stage_resolves_to_a_contract(self, registry) -> None:
        from core.pipeline_orchestrator import PipelineOrchestrator
        from schemas.stage import STAGE_NAMES
        orch = PipelineOrchestrator()
        for stage in STAGE_NAMES:
            contract_name = orch.resolve_contract_name(stage)
            contract = registry.resolve(contract_name)
            assert contract is not None, f"stage {stage} -> {contract_name} not registered"

    def test_orchestrator_is_tutorial_branded(self, registry) -> None:
        orch_contract = registry.resolve("tutorial_orchestrator")
        assert "Tutorial Builder" in orch_contract.system_instructions
        assert "life event" not in orch_contract.system_instructions.lower()


class TestPromptAssembly:
    def _assembler(self, registry):
        from core.prompt_assembler import PromptAssembler
        return PromptAssembler(registry.resolve("tutorial_orchestrator"))

    def test_framing_prompt_includes_tutorial_fields(self, registry) -> None:
        assembler = self._assembler(registry)
        contract = registry.resolve("tutorial_framing_core")
        prompt = assembler.assemble(contract, SAMPLE_PAYLOAD)
        assert "TUTORIAL REQUEST: Build a SaaS landing page" in prompt.user_message
        assert "SKILL LEVEL: beginner" in prompt.user_message
        assert "STACK / LANGUAGE / FRAMEWORK: Next.js 14, Tailwind CSS" in prompt.user_message
        assert "INCLUDE CODE SNIPPETS: yes" in prompt.user_message
        assert "life event" not in prompt.user_message.lower()
        assert "life event" not in prompt.system_message.lower()

    def test_outline_prompt_renders_with_upstream(self, registry) -> None:
        assembler = self._assembler(registry)
        contract = registry.resolve("document_outline")
        upstream = {
            "system_architecture": {
                "system_name": "Build a SaaS Landing Page with Next.js and Tailwind",
                "topic": SAMPLE_PAYLOAD["topic"],
                "control_domains": [{"id": "domain-01", "name": "Project Scaffold"}],
            }
        }
        prompt = assembler.assemble(contract, SAMPLE_PAYLOAD, upstream_outputs=upstream)
        assert "Tutorial Request: Build a SaaS landing page" in prompt.user_message
        assert "Project Scaffold" in prompt.user_message

    def test_all_stage_contracts_assemble_without_error(self, registry) -> None:
        from core.pipeline_orchestrator import PipelineOrchestrator, STAGE_CONTRACT_MAP
        from schemas.stage import STAGE_NAMES
        assembler = self._assembler(registry)
        orch = PipelineOrchestrator()
        upstream = {s: {"placeholder": True} for s in STAGE_NAMES}
        for stage in STAGE_NAMES:
            contract = registry.resolve(STAGE_CONTRACT_MAP[stage])
            payload = {
                **SAMPLE_PAYLOAD,
                # loop_per_chapter contracts use extra per-chapter keys
                "current_chapter_json": "{}",
                "chapter_narrative": "",
                "chapter_number": 1,
                "domain_name": "Project Scaffold",
                "document_title": "Test Tutorial",
                "narrative_fix_instructions": "",
                "structure_fix_instructions": "",
            }
            prompt = assembler.assemble(contract, payload, upstream_outputs=upstream)
            assert prompt.user_message, f"empty user message for stage {stage}"
            assert "life event" not in prompt.system_message.lower(), f"stale life-event language in {stage}"


class TestNarrativeHeadingChecks:
    TUTORIAL_NARRATIVE = (
        "## What You're Building\nA landing page scaffold.\n\n"
        "## Step-by-Step Implementation\n1. Run the command.\n\n"
        "```bash\n" + "npx create-next-app@14 landing --ts --tailwind --app " * 40 + "\n```\n\n"
        "## How It Works\nExplanation.\n\n"
        "## Common Mistakes and Debugging\nFixes.\n\n"
        "## Checkpoint and Hand-off\nVerify and continue."
    )

    def test_new_headings_pass(self) -> None:
        from services.pipeline_service import PipelineService
        defects = PipelineService._chapter_narrative_defects(self.TUTORIAL_NARRATIVE)
        assert defects == [], f"unexpected defects: {defects}"

    def test_old_headings_fail(self) -> None:
        from services.pipeline_service import PipelineService
        old = "## Orientation Snapshot\nText.\n\n## Immediate Execution Path\nText."
        defects = PipelineService._chapter_narrative_defects(old)
        assert any("What You're Building" in d for d in defects)

    def test_code_blocks_excluded_from_paragraph_density(self) -> None:
        from services.pipeline_service import PipelineService
        defects = PipelineService._chapter_narrative_defects(self.TUTORIAL_NARRATIVE)
        assert not any("exceed 140 words" in d for d in defects)


class TestProjectCreateSchema:
    def test_accepts_camel_case_tutorial_fields(self) -> None:
        from schemas.project import ProjectCreate
        body = ProjectCreate.model_validate({
            "title": "My Tutorial",
            "topic": "Create a Discord bot with Python",
            "skillLevel": "beginner",
            "tutorialType": "hands-on build",
            "stack": "Python, discord.py",
            "includeCode": True,
            "outputStyle": "checklist-driven",
            "constraints": "free hosting only",
        })
        assert body.topic == "Create a Discord bot with Python"
        assert body.skill_level == "beginner"
        assert body.include_code is True

    def test_topic_required_and_non_empty(self) -> None:
        from schemas.project import ProjectCreate
        with pytest.raises(Exception):
            ProjectCreate.model_validate({"title": "X", "topic": "   "})
