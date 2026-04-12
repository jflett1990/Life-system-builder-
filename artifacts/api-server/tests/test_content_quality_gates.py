from render.document_sanitizer import run_quality_gates


def _chapter(**overrides):
    base = {
        "chapter_number": 1,
        "chapter_opener": {
            "what_this_is_for": "Coordinate medication and provider communication.",
            "when_it_matters": "At discharge and during weekly care-plan updates.",
            "failure_looks_like": "Missed medication changes and unplanned ER visits.",
            "produces": ["Verified medication baseline"],
            "do_first": ["Retrieve discharge medication reconciliation"],
        },
        "minimum_viable_actions": ["Call pharmacy", "Confirm doses"],
        "decision_guide": [{"decision": "Escalate", "if_condition": "A", "then_action": "B", "else_action": "C"}, {"decision": "Coverage", "if_condition": "X", "then_action": "Y", "else_action": "Z"}],
        "trigger_blocks": ["If prescription changes, update care team immediately."],
        "risk_blocks": ["Delayed updates can cause duplicate dosing."],
        "worksheet_linkage": [{"worksheet_title": "Medication Log", "use_when": "After any care change", "unblocks": "Updated shift handoff"}],
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
                )
            ]
        }
    }
    result = run_quality_gates([], outputs)
    assert result.passed is False
    assert any(f.startswith("QG5:") for f in result.failures)
    assert any(f.startswith("QG6:") for f in result.failures)
    assert any(f.startswith("QG7:") for f in result.failures)
