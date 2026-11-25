from fastapi import APIRouter, HTTPException, Header
from trace_ai.delivery.storage_backend import get_contract, get_pending_review
from trace_ai.normalization.schema import ExtractionStatus
from trace_ai.common.logger import log
from trace_ai.config import config

router = APIRouter(prefix="/api/v1", tags=["contracts"])


def _verify_api_key(x_api_key: str | None) -> None:
    if not config.REST_API_KEY:
        return
    if x_api_key != config.REST_API_KEY:
        log("Unauthorized API request -- invalid or missing API key", severity="WARNING")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.get("/contracts/{contract_id}")
async def get_contract_by_id(contract_id: str, x_api_key: str | None = Header(default=None)):
    _verify_api_key(x_api_key)
    data = get_contract(contract_id)
    if not data:
        log("Contract not found via REST API", severity="WARNING", contract_id=contract_id)
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    log("Contract fetched via REST API", severity="DEBUG", contract_id=contract_id)
    return data


@router.get("/contracts")
async def list_contracts_by_status(
    status: str | None = None,
    x_api_key: str | None = Header(default=None),
):
    _verify_api_key(x_api_key)

    if status:
        try:
            ExtractionStatus(status)
        except ValueError:
            valid = [s.value for s in ExtractionStatus]
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")

    if status == ExtractionStatus.REVIEW_REQUIRED.value:
        contracts = get_pending_review()
    else:
        log("List by arbitrary status not supported -- use status=Review Required or fetch by ID", severity="WARNING")
        raise HTTPException(status_code=400, detail="Only status='Review Required' is supported for listing. Fetch individual contracts by ID.")

    log("Contracts listed via REST API", severity="DEBUG", status=status, count=len(contracts))
    return {"contracts": contracts, "count": len(contracts)}
