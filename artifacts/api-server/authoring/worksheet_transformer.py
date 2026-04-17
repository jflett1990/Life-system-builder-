"""
WorksheetTransformer — Stage 2.5 deterministic transform.

PDR §04 Stage 2.5:
  Zero LLM calls. Pure data transformation.
  Converts worksheet_seeds from strategy_blueprint into fully structured
  worksheet_packets. Pre-populates fields where data is unambiguous:
    - Contact sheets: pre-fill roles and names from project_brief entities
    - Timeline trackers: pre-fill milestone rows from strategy_blueprint milestones
    - Escalation matrices: pre-fill trigger conditions from risk_gates

This stage makes the LLM waste explicit by separating it out. Worksheets
follow predictable schemas per type; generating them from scratch with an
LLM burns premium capacity for work that is a deterministic transform.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from models.v2_artifacts import (
    WorksheetPacket,
    WorksheetSeed,
    ColumnDefinition,
    WorksheetRow,
)

logger = get_logger(__name__)


# ── Worksheet type schemas ──────────────────────────────────────────────────────

def _task_tracker_columns() -> list[ColumnDefinition]:
    return [
        ColumnDefinition(name="Task", col_type="text", width_hint="40%"),
        ColumnDefinition(name="Owner", col_type="owner_select", width_hint="20%"),
        ColumnDefinition(name="Due Date", col_type="date", width_hint="15%"),
        ColumnDefinition(name="Status", col_type="status_badge", width_hint="15%"),
        ColumnDefinition(name="Notes", col_type="text", width_hint="10%"),
    ]


def _contact_sheet_columns() -> list[ColumnDefinition]:
    return [
        ColumnDefinition(name="Name", col_type="text", width_hint="25%"),
        ColumnDefinition(name="Role", col_type="text", width_hint="20%"),
        ColumnDefinition(name="Phone", col_type="text", width_hint="20%"),
        ColumnDefinition(name="Email", col_type="text", width_hint="20%"),
        ColumnDefinition(name="Notes", col_type="text", width_hint="15%"),
    ]


def _decision_log_columns() -> list[ColumnDefinition]:
    return [
        ColumnDefinition(name="Decision", col_type="text", width_hint="35%"),
        ColumnDefinition(name="Date", col_type="date", width_hint="15%"),
        ColumnDefinition(name="Made By", col_type="owner_select", width_hint="20%"),
        ColumnDefinition(name="Outcome", col_type="text", width_hint="20%"),
        ColumnDefinition(name="Review Date", col_type="date", width_hint="10%"),
    ]


def _escalation_matrix_columns() -> list[ColumnDefinition]:
    return [
        ColumnDefinition(name="Trigger Condition", col_type="text", width_hint="35%"),
        ColumnDefinition(name="Severity", col_type="status_badge", width_hint="15%"),
        ColumnDefinition(name="First Contact", col_type="owner_select", width_hint="20%"),
        ColumnDefinition(name="Escalate To", col_type="owner_select", width_hint="20%"),
        ColumnDefinition(name="Response Window", col_type="text", width_hint="10%"),
    ]


def _timeline_tracker_columns() -> list[ColumnDefinition]:
    return [
        ColumnDefinition(name="Milestone", col_type="text", width_hint="35%"),
        ColumnDefinition(name="Target Date", col_type="date", width_hint="15%"),
        ColumnDefinition(name="Responsible", col_type="owner_select", width_hint="20%"),
        ColumnDefinition(name="Dependencies", col_type="text", width_hint="20%"),
        ColumnDefinition(name="Done", col_type="yn_circle", width_hint="10%"),
    ]


COLUMN_BUILDERS: dict[str, Any] = {
    "task_tracker":       _task_tracker_columns,
    "contact_sheet":      _contact_sheet_columns,
    "decision_log":       _decision_log_columns,
    "escalation_matrix":  _escalation_matrix_columns,
    "timeline_tracker":   _timeline_tracker_columns,
}


# ── Pre-population helpers ─────────────────────────────────────────────────────

def _prefill_contact_rows(
    seed: WorksheetSeed,
    brief: dict[str, Any],
) -> list[WorksheetRow]:
    rows: list[WorksheetRow] = []
    # Derive contacts from project brief people entities
    for i, person in enumerate(brief.get("people", [])):
        rows.append(WorksheetRow(
            row_id=f"{seed.seed_id}-r{i+1:02d}",
            cells={
                "Name":  person.get("name", ""),
                "Role":  person.get("role", ""),
                "Phone": person.get("contact", ""),
                "Email": "",
                "Notes": "",
            },
            is_prefilled=bool(person.get("name") or person.get("role")),
        ))
    # Pad to at least 8 rows
    while len(rows) < 8:
        rows.append(WorksheetRow(
            row_id=f"{seed.seed_id}-r{len(rows)+1:02d}",
            cells={"Name": "", "Role": "", "Phone": "", "Email": "", "Notes": ""},
        ))
    return rows


def _prefill_timeline_rows(
    seed: WorksheetSeed,
    milestones: list[dict[str, Any]],
) -> list[WorksheetRow]:
    rows: list[WorksheetRow] = []
    for i, m in enumerate(milestones):
        milestone_id = m.get("milestone_id", "")
        if seed.source_milestones and milestone_id not in seed.source_milestones:
            continue
        rows.append(WorksheetRow(
            row_id=f"{seed.seed_id}-r{i+1:02d}",
            cells={
                "Milestone":    m.get("label", ""),
                "Target Date":  m.get("deadline_description", ""),
                "Responsible":  m.get("responsible_role", ""),
                "Dependencies": ", ".join(m.get("dependencies", [])),
                "Done":         "",
            },
            is_prefilled=bool(m.get("label")),
        ))
    while len(rows) < 6:
        rows.append(WorksheetRow(
            row_id=f"{seed.seed_id}-r{len(rows)+1:02d}",
            cells={"Milestone": "", "Target Date": "", "Responsible": "", "Dependencies": "", "Done": ""},
        ))
    return rows


def _prefill_escalation_rows(
    seed: WorksheetSeed,
    risk_gates: list[dict[str, Any]],
) -> list[WorksheetRow]:
    rows: list[WorksheetRow] = []
    for i, gate in enumerate(risk_gates):
        gate_id = gate.get("gate_id", "")
        if seed.source_risk_gates and gate_id not in seed.source_risk_gates:
            continue
        rows.append(WorksheetRow(
            row_id=f"{seed.seed_id}-r{i+1:02d}",
            cells={
                "Trigger Condition": gate.get("condition", ""),
                "Severity":          "High",
                "First Contact":     "",
                "Escalate To":       gate.get("escalation_path", ""),
                "Response Window":   "",
            },
            is_prefilled=bool(gate.get("condition")),
        ))
    while len(rows) < 5:
        rows.append(WorksheetRow(
            row_id=f"{seed.seed_id}-r{len(rows)+1:02d}",
            cells={"Trigger Condition": "", "Severity": "", "First Contact": "", "Escalate To": "", "Response Window": ""},
        ))
    return rows


def _blank_rows(seed_id: str, columns: list[ColumnDefinition], count: int = 8) -> list[WorksheetRow]:
    return [
        WorksheetRow(
            row_id=f"{seed_id}-r{i+1:02d}",
            cells={col.name: "" for col in columns},
        )
        for i in range(count)
    ]


# ── WorksheetTransformer ───────────────────────────────────────────────────────

class WorksheetTransformer:
    """Deterministic Stage 2.5 transform: worksheet_seeds → worksheet_packets.

    No LLM calls. Pure data transformation from strategy blueprint entities.
    """

    def transform(
        self,
        seeds: list[WorksheetSeed | dict[str, Any]],
        *,
        brief: dict[str, Any] | None = None,
        milestones: list[dict[str, Any]] | None = None,
        risk_gates: list[dict[str, Any]] | None = None,
    ) -> list[WorksheetPacket]:
        brief = brief or {}
        milestones = milestones or []
        risk_gates = risk_gates or []
        packets: list[WorksheetPacket] = []

        for raw_seed in seeds:
            seed = WorksheetSeed(**raw_seed) if isinstance(raw_seed, dict) else raw_seed
            packet = self._transform_seed(seed, brief=brief, milestones=milestones, risk_gates=risk_gates)
            packets.append(packet)
            logger.debug(
                "worksheet_transform | seed=%s type=%s rows=%d prefilled=%d",
                seed.seed_id, seed.worksheet_type,
                len(packet.rows),
                sum(1 for r in packet.rows if r.is_prefilled),
            )

        logger.info(
            "worksheet_transform | %d seeds → %d packets | zero LLM calls",
            len(seeds), len(packets),
        )
        return packets

    def _transform_seed(
        self,
        seed: WorksheetSeed,
        brief: dict[str, Any],
        milestones: list[dict[str, Any]],
        risk_gates: list[dict[str, Any]],
    ) -> WorksheetPacket:
        ws_type = seed.worksheet_type
        column_builder = COLUMN_BUILDERS.get(ws_type)
        columns = column_builder() if column_builder else [
            ColumnDefinition(name="Item", col_type="text"),
            ColumnDefinition(name="Notes", col_type="text"),
        ]

        # Pre-populate rows based on worksheet type
        if ws_type == "contact_sheet":
            rows = _prefill_contact_rows(seed, brief)
        elif ws_type == "timeline_tracker":
            rows = _prefill_timeline_rows(seed, milestones)
        elif ws_type == "escalation_matrix":
            rows = _prefill_escalation_rows(seed, risk_gates)
        else:
            rows = _blank_rows(seed.seed_id, columns)

        return WorksheetPacket(
            worksheet_id=seed.seed_id,
            worksheet_type=ws_type,
            domain_id=seed.domain_id,
            title=seed.title,
            purpose="",
            columns=columns,
            rows=rows,
            instructions_block=None,
        )
