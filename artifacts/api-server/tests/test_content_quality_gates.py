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
        "minimum_viable_actions": ["Action 1", "Action 2", "Action 3", "Action 4"],
        "operational_sections": [
            {"section_id": "A", "section_title": "Topic A", "explanation": ["Paragraph"], "key_operational_considerations": ["A", "B", "C"], "common_failure_modes": ["A", "B", "C"], "process_steps": ["1", "2", "3"]},
            {"section_id": "B", "section_title": "Topic B", "explanation": ["Paragraph"], "key_operational_considerations": ["A", "B", "C"], "common_failure_modes": ["A", "B", "C"], "process_steps": ["1", "2", "3"]},
            {"section_id": "C", "section_title": "Topic C", "explanation": ["Paragraph"], "key_operational_considerations": ["A", "B", "C"], "common_failure_modes": ["A", "B", "C"], "process_steps": ["1", "2", "3"]},
            {"section_id": "D", "section_title": "Topic D", "explanation": ["Paragraph"], "key_operational_considerations": ["A", "B", "C"], "common_failure_modes": ["A", "B", "C"], "process_steps": ["1", "2", "3"]},
        ],
        "worksheet_linkage": [{"worksheet_title": "Medication Log", "use_when": "After any care change", "unblocks": "Updated shift handoff"}],
        "orientation_snapshot": "Orientation paragraph one.\n\nOrientation paragraph two with clear decision context.",
        "narrative": "Orientation paragraph one.\n\nOrientation paragraph two with clear decision context.",
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
                    operational_sections=[],
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
