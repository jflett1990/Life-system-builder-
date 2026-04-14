from render.document_model import FRONT_MATTER_SEQUENCE, build_manual_document
from render.composition_engine import compose_manual
from render.validation_report import validate_manual


def _sample_outputs():
    return {
        "system_architecture": {
            "system_name": "Ops Manual",
            "system_objective": "Control execution",
            "control_domains": [{"id": "dom-01", "name": "Domain A", "purpose": "Purpose"}],
        },
        "chapter_expansion": {
            "chapters": [
                {
                    "chapter_number": 1,
                    "chapter_title": "Chapter 1",
                    "domain_id": "dom-01",
                    "chapter_opener": {"when_it_matters": "Now", "promise": "Do this"},
                    "minimum_viable_actions": ["Action"],
                    "risk_blocks": ["Risk"],
                    "decision_guide": ["Decide"],
                }
            ]
        },
        "chapter_worksheets": {
            "chapters": [
                {
                    "chapter_number": 1,
                    "worksheets": [{"id": "ws-01-01", "title": "Sheet", "usage_tag": "COMPLETE EARLY"}],
                }
            ]
        },
    }


def test_front_matter_order_is_locked():
    manual = build_manual_document(1, _sample_outputs())
    assert [m["id"] for m in manual.front_matter] == FRONT_MATTER_SEQUENCE


def test_composition_and_validation_pass_for_sample():
    manual = build_manual_document(1, _sample_outputs())
    composed = compose_manual(manual)
    report = validate_manual(manual, composed)
    assert report.build_status == "pass"
    assert report.stats["chapter_count"] == 1
    assert report.stats["worksheet_count"] == 1
