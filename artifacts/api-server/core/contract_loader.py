"""
ContractLoader — reads, validates, and returns ContractDefinition objects from disk.
Contracts are never imported directly into service code. All access is through this loader.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"

REQUIRED_KEYS = {"name", "version", "description", "output_mode", "upstream_dependencies"}
VALID_OUTPUT_MODES = {"json", "markdown_json"}


@dataclass
class ContractDefinition:
    name: str
    version: str
    stage: str | None
    description: str
    output_mode: str
    upstream_dependencies: list[str]
    system_instructions: str | None
    user_prompt_template: str | None
    output_schema: dict[str, Any] | None
    required_output_fields: list[str]
    raw: dict[str, Any] = field(repr=False)

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"

    def has_prompt(self) -> bool:
        return self.user_prompt_template is not None

    def is_orchestrator(self) -> bool:
        return self.stage is None


class ContractValidationError(Exception):
    """Raised when a contract file fails structural validation."""


def _validate_structure(data: dict[str, Any], filepath: Path) -> None:
    """Compiler-style validator — raises ContractValidationError on any issue."""
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ContractValidationError(
            f"{filepath.name}: missing required keys: {sorted(missing)}"
        )

    if data["output_mode"] not in VALID_OUTPUT_MODES:
        raise ContractValidationError(
            f"{filepath.name}: invalid output_mode '{data['output_mode']}'. "
            f"Must be one of: {sorted(VALID_OUTPUT_MODES)}"
        )

    if not isinstance(data.get("upstream_dependencies", []), list):
        raise ContractValidationError(
            f"{filepath.name}: 'upstream_dependencies' must be a list"
        )

    if not isinstance(data.get("required_output_fields", []), list):
        raise ContractValidationError(
            f"{filepath.name}: 'required_output_fields' must be a list"
        )

    # Non-orchestrator contracts must have system_instructions
    if data.get("stage") is not None and not data.get("system_instructions"):
        raise ContractValidationError(
            f"{filepath.name}: stage contracts must have 'system_instructions'"
        )


def load_contract(filepath: Path) -> ContractDefinition:
    """Load and validate a single contract file from disk."""
    if not filepath.exists():
        raise FileNotFoundError(f"Contract file not found: {filepath}")

    try:
        data: dict[str, Any] = json.loads(filepath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"{filepath.name}: invalid JSON — {e}") from e

    _validate_structure(data, filepath)

    contract = ContractDefinition(
        name=data["name"],
        version=data["version"],
        stage=data.get("stage"),
        description=data["description"],
        output_mode=data["output_mode"],
        upstream_dependencies=data.get("upstream_dependencies", []),
        system_instructions=data.get("system_instructions"),
        user_prompt_template=data.get("user_prompt_template"),
        output_schema=data.get("output_schema"),
        required_output_fields=data.get("required_output_fields", []),
        raw=data,
    )
    logger.debug("Loaded contract %s v%s from %s", contract.name, contract.version, filepath.name)
    return contract


def load_registry() -> dict:
    """Load and return the registry.json index."""
    registry_path = CONTRACTS_DIR / "registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"Contract registry not found: {registry_path}")
    return json.loads(registry_path.read_text(encoding="utf-8"))


def load_all_from_registry() -> list[ContractDefinition]:
    """Load every contract referenced in registry.json."""
    registry = load_registry()
    contracts: list[ContractDefinition] = []

    for entry in registry.get("contracts", []):
        file_rel = entry.get("file")
        if not file_rel:
            raise ContractValidationError(f"Registry entry missing 'file': {entry}")

        filepath = CONTRACTS_DIR / file_rel
        contract = load_contract(filepath)

        # Cross-check: registry name/version must match file content
        if contract.name != entry["name"]:
            raise ContractValidationError(
                f"Registry name '{entry['name']}' does not match file name '{contract.name}' in {filepath.name}"
            )
        if contract.version != entry["version"]:
            raise ContractValidationError(
                f"Registry version '{entry['version']}' does not match file version '{contract.version}' in {filepath.name}"
            )

        contracts.append(contract)

    logger.info("Loaded %d contracts from registry", len(contracts))
    return contracts
