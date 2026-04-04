"""
Contracts inspection endpoints.

Read-only — returns loaded contract definitions from the registry.
No LLM calls, no DB writes.
"""
from fastapi import APIRouter, HTTPException

from core.contract_registry import get_registry, ContractRegistryError

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("")
def list_contracts():
    """List all registered prompt contracts (name, version, stage, output_mode)."""
    return {"contracts": get_registry().summary()}


@router.get("/{name}")
def get_contract(name: str, version: str | None = None):
    """Get full contract definition by name (and optional version)."""
    try:
        contract = get_registry().resolve(name, version)
        return contract.raw
    except ContractRegistryError as e:
        raise HTTPException(status_code=404, detail=str(e))
