from __future__ import annotations

COMPONENT_LIBRARY: dict[str, dict[str, object]] = {
    "CoverBlock": {"semantic_role": "cover", "allowed_nesting": ["cover"], "spacing_rules": "fixed", "pagination_rules": "force_page_break_before", "print_rules": "full_bleed_safe", "min_height": 120, "max_height": 700},
    "DisclaimerBlock": {"semantic_role": "legal_notice", "allowed_nesting": ["disclaimer"], "spacing_rules": "normal", "pagination_rules": "keep_together", "print_rules": "grayscale", "min_height": 80, "max_height": 400},
    "AboutBlock": {"semantic_role": "orientation", "allowed_nesting": ["about"], "spacing_rules": "normal", "pagination_rules": "keep_together", "print_rules": "grayscale", "min_height": 80, "max_height": 500},
    "ContentsBlock": {"semantic_role": "navigation", "allowed_nesting": ["contents"], "spacing_rules": "compact", "pagination_rules": "keep_together", "print_rules": "grayscale", "min_height": 100, "max_height": 600},
    "DomainTable": {"semantic_role": "taxonomy", "allowed_nesting": ["operating_model"], "spacing_rules": "normal", "pagination_rules": "table_header_keep", "print_rules": "thin_rules", "min_height": 60, "max_height": 900},
    "MasterRulesTable": {"semantic_role": "rules", "allowed_nesting": ["master_operating_rules"], "spacing_rules": "normal", "pagination_rules": "table_header_keep", "print_rules": "thin_rules", "min_height": 60, "max_height": 900},
    "CascadeChainTable": {"semantic_role": "dependency_logic", "allowed_nesting": ["cascade_chain"], "spacing_rules": "normal", "pagination_rules": "table_header_keep", "print_rules": "thin_rules", "min_height": 60, "max_height": 900},
    "ChapterOpener": {"semantic_role": "chapter_intro", "allowed_nesting": ["chapter_opener"], "spacing_rules": "airy", "pagination_rules": "force_page_break_before", "print_rules": "chapter_bar", "min_height": 120, "max_height": 700},
    "BodySection": {"semantic_role": "instruction", "allowed_nesting": ["chapter_body"], "spacing_rules": "normal", "pagination_rules": "widow_orphan_control", "print_rules": "body_text", "min_height": 40, "max_height": 900},
    "ScenarioBox": {"semantic_role": "scenario", "allowed_nesting": ["chapter_body"], "spacing_rules": "boxed", "pagination_rules": "keep_together_short", "print_rules": "soft_fill", "min_height": 60, "max_height": 500},
    "WarningBox": {"semantic_role": "warning", "allowed_nesting": ["chapter_body"], "spacing_rules": "boxed", "pagination_rules": "keep_together", "print_rules": "soft_fill", "min_height": 60, "max_height": 500},
    "KeyInsightBox": {"semantic_role": "insight", "allowed_nesting": ["chapter_body"], "spacing_rules": "boxed", "pagination_rules": "keep_together", "print_rules": "soft_fill", "min_height": 60, "max_height": 500},
    "ChecklistBlock": {"semantic_role": "checklist", "allowed_nesting": ["chapter_body", "worksheet_page"], "spacing_rules": "normal", "pagination_rules": "title_with_first_two_lines", "print_rules": "checkbox", "min_height": 60, "max_height": 900},
    "WorksheetHeader": {"semantic_role": "worksheet_identity", "allowed_nesting": ["worksheet_page"], "spacing_rules": "normal", "pagination_rules": "keep_with_first_cluster", "print_rules": "metadata_tag", "min_height": 80, "max_height": 240},
    "WorksheetTable": {"semantic_role": "worksheet_input", "allowed_nesting": ["worksheet_page"], "spacing_rules": "normal", "pagination_rules": "keep_together_unless_multi_page", "print_rules": "line_weight_safe", "min_height": 120, "max_height": 1400},
    "WorksheetForm": {"semantic_role": "worksheet_input", "allowed_nesting": ["worksheet_page"], "spacing_rules": "normal", "pagination_rules": "keep_together", "print_rules": "line_weight_safe", "min_height": 120, "max_height": 1200},
    "WorksheetMatrix": {"semantic_role": "worksheet_input", "allowed_nesting": ["worksheet_page"], "spacing_rules": "normal", "pagination_rules": "keep_together", "print_rules": "line_weight_safe", "min_height": 120, "max_height": 1200},
    "ReviewCalendarTable": {"semantic_role": "cadence", "allowed_nesting": ["review_cadence"], "spacing_rules": "compact", "pagination_rules": "table_header_keep", "print_rules": "thin_rules", "min_height": 100, "max_height": 1000},
    "DecisionFrameworkTable": {"semantic_role": "decision", "allowed_nesting": ["decision_framework"], "spacing_rules": "compact", "pagination_rules": "table_header_keep", "print_rules": "thin_rules", "min_height": 100, "max_height": 1000},
    "QuickIndexBlock": {"semantic_role": "emergency_nav", "allowed_nesting": ["emergency_navigation", "appendix"], "spacing_rules": "compact", "pagination_rules": "force_page_break_before", "print_rules": "grayscale", "min_height": 80, "max_height": 1200},
}
