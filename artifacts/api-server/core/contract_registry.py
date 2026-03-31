"""
ContractRegistry — singleton registry mapping name@version to ContractDefinition.

Usage:
    registry = get_registry()
    contract = registry.resolve("life_event_system_core")
    orchestrator = registry.resolve("life_system_orchestrator")

Call validate_and_load() once at app startup. Subsequent calls to get_registry()
return the cached singleton without re-reading disk.
"""
from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING

from core.logging import get_logger

if TYPE_CHECKING:
    from core.contract_loader import ContractDefinition

logger = get_logger(__name__)

_registry_instance: "ContractRegistry | None" = None
_registry_lock = Lock()


class ContractRegistryError(Exception):
    """Raised when a contract cannot be resolved."""


class ContractRegistry:
    """Thread-safe in-memory registry of loaded contract definitions."""

    def __init__(self) -> None:
        # name -> {version -> ContractDefinition}
        self._store: dict[str, dict[str, "ContractDefinition"]] = {}
        # name -> latest version string (insertion order = registry.json order)
        self._latest: dict[str, str] = {}

    def register(self, contract: "ContractDefinition") -> None:
        if contract.name not in self._store:
            self._store[contract.name] = {}
        self._store[contract.name][contract.version] = contract
        # Last registered version wins as "latest" — registry.json should be ordered
        self._latest[contract.name] = contract.version
        logger.debug("Registered contract %s", contract.key)

    def resolve(self, name: str, version: str | None = None) -> "ContractDefinition":
        """Return a contract by name and optional version. Defaults to latest."""
        if name not in self._store:
            available = sorted(self._store.keys())
            raise ContractRegistryError(
                f"Contract '{name}' not found. Available: {available}"
            )
        versions = self._store[name]
        target_version = version or self._latest[name]
        if target_version not in versions:
            raise ContractRegistryError(
                f"Contract '{name}' version '{target_version}' not found. "
                f"Available versions: {sorted(versions.keys())}"
            )
        return versions[target_version]

    def resolve_by_stage(self, stage_name: str) -> "ContractDefinition":
        """Find the contract responsible for a given pipeline stage name."""
        for versions in self._store.values():
            for contract in versions.values():
                if contract.stage == stage_name:
                    return contract
        raise ContractRegistryError(
            f"No contract found for stage '{stage_name}'"
        )

    def list_all(self) -> list["ContractDefinition"]:
        return [
            contract
            for versions in self._store.values()
            for contract in versions.values()
        ]

    def summary(self) -> list[dict]:
        return [
            {
                "name": c.name,
                "version": c.version,
                "stage": c.stage,
                "description": c.description,
                "output_mode": c.output_mode,
                "upstream_dependencies": c.upstream_dependencies,
                "has_prompt": c.has_prompt(),
            }
            for c in self.list_all()
        ]


def validate_and_load() -> ContractRegistry:
    """
    Load all contracts from disk, validate them, and populate the global registry.
    Call this once at application startup. Raises on any validation failure so the
    app fails fast rather than serving broken prompts.
    """
    from core.contract_loader import load_all_from_registry, ContractValidationError  # noqa

    global _registry_instance

    with _registry_lock:
        if _registry_instance is not None:
            logger.info("Contract registry already loaded — reusing")
            return _registry_instance

        logger.info("Loading contract registry...")
        contracts = load_all_from_registry()

        registry = ContractRegistry()
        for contract in contracts:
            registry.register(contract)

        _registry_instance = registry
        logger.info(
            "Contract registry ready: %d contracts registered",
            len(contracts),
        )
        return registry


def get_registry() -> ContractRegistry:
    """Return the loaded registry singleton. Must call validate_and_load() first."""
    if _registry_instance is None:
        raise RuntimeError(
            "ContractRegistry not initialised. Call validate_and_load() at app startup."
        )
    return _registry_instance
