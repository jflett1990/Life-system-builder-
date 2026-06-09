from render.document_sanitizer import run_quality_gates


def _chapter(**overrides):
    base = {
        "chapter_number": 1,
        "chapter_opener": {
            "what_this_is_for": "Scaffold the Next.js project and configure Tailwind.",
            "when_it_matters": "First step — every later module builds on this scaffold.",
            "failure_looks_like": "Dev server starts but pages render unstyled HTML.",
            "produces": ["Running dev server with Tailwind applied"],
            "do_first": ["Run create-next-app with the --tailwind flag"],
        },
        "minimum_viable_actions": ["Run create-next-app", "Verify node version", "Start the dev server"],
        "decision_guide": [{"decision": "Package manager", "if_condition": "A", "then_action": "B", "else_action": "C"}, {"decision": "Node version", "if_condition": "X", "then_action": "Y", "else_action": "Z"}, {"decision": "TypeScript", "if_condition": "R", "then_action": "S", "else_action": "T"}],
        "trigger_blocks": ["If the build fails with a module-not-found error, delete node_modules and reinstall.", "If port 3000 is taken, stop the other process or use a different port."],
        "risk_blocks": ["Running install in the wrong directory creates a second package.json.", "Missing content globs silently drop Tailwind styles."],
        "worksheet_linkage": [{"worksheet_title": "Dev Environment Verification Checklist", "use_when": "After the scaffold completes", "unblocks": "Building the first page"}],
        "detailed_explanation": "## How It Fits Together\nThis is a controlled deep explanation section that remains readable and stack-specific.",
        "narrative": "## What You're Building\nClear orientation.\n\n## Step-by-Step Implementation\nActions.\n\n## How It Works\nDetails.\n\n## Common Mistakes and Debugging\nRecovery.\n\n## Checkpoint and Hand-off\nHandoffs.",
    }
    base.update(overrides)
    return base


def test_quality_gates_pass_with_structured_chapters():
    outputs = {"chapter_expansion": {"chapters": [_chapter()]}}
    result = run_quality_gates([], outputs)
    assert result.passed is True
    assert result.failures == []


def test_quality_gates_fail_on_missing_orientation_and_action_structure():
    outputs = {
        "chapter_expansion": {
            "chapters": [
                _chapter(
                    chapter_opener={},
                    minimum_viable_actions=[],
                    decision_guide=[],
                    trigger_blocks=[],
                    risk_blocks=[],
                    worksheet_linkage=[],
                    detailed_explanation="",
                )
            ]
        }
    }
    result = run_quality_gates([], outputs)
    assert result.passed is False
    assert any(f.startswith("QG5:") for f in result.failures)
    assert any(f.startswith("QG6:") for f in result.failures)
    assert any(f.startswith("QG7:") for f in result.failures)
    assert any(f.startswith("QG8:") for f in result.failures)
