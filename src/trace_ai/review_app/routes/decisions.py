from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from trace_ai.delivery.storage_backend import list_contracts
from trace_ai.normalization.schema import ExtractionStatus
from trace_ai.common.logger import log
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/approved", response_class=HTMLResponse)
async def approved(request: Request):
    contracts = list_contracts(ExtractionStatus.APPROVED.value)
    contracts.sort(key=lambda c: c.get("reviewed_at") or "", reverse=True)
    log("Approved contracts fetched", severity="DEBUG", count=len(contracts))
    return templates.TemplateResponse("decisions.html", {
        "request": request,
        "contracts": contracts,
        "status": ExtractionStatus.APPROVED.value,
    })


@router.get("/rejected", response_class=HTMLResponse)
async def rejected(request: Request):
    contracts = list_contracts(ExtractionStatus.REJECTED.value)
    contracts.sort(key=lambda c: c.get("reviewed_at") or "", reverse=True)
    log("Rejected contracts fetched", severity="DEBUG", count=len(contracts))
    return templates.TemplateResponse("decisions.html", {
        "request": request,
        "contracts": contracts,
        "status": ExtractionStatus.REJECTED.value,
    })
