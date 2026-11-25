from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from trace_ai.delivery.storage_backend import get_contract, update_review_decision
from trace_ai.delivery.gcs_writer import write
from trace_ai.normalization.schema import ContractRecord
from trace_ai.common.logger import log
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/review/{contract_id}", response_class=HTMLResponse)
async def review_detail(request: Request, contract_id: str):
    data = get_contract(contract_id)
    if not data:
        log("Contract not found for review", severity="WARNING", contract_id=contract_id)
        raise HTTPException(status_code=404, detail="Contract not found")
    log("Review detail fetched", severity="DEBUG", contract_id=contract_id)
    return templates.TemplateResponse("review.html", {"request": request, "contract": data})


@router.post("/review/{contract_id}")
async def submit_review(
    contract_id: str,
    reviewer: str = Form(...),
    decision: str = Form(...),
    notes: str = Form(default=""),
):
    if decision not in ("Approved", "Rejected"):
        log("Invalid review decision submitted", severity="ERROR", contract_id=contract_id, decision=decision)
        raise HTTPException(status_code=400, detail="Decision must be Approved or Rejected")

    data = get_contract(contract_id)
    if not data:
        log("Contract not found on review submit", severity="ERROR", contract_id=contract_id)
        raise HTTPException(status_code=404, detail="Contract not found")

    update_review_decision(contract_id, reviewer, decision, notes)
    log("Review decision submitted", contract_id=contract_id, decision=decision, reviewer=reviewer)

    if decision == "Approved":
        record = ContractRecord(**data)
        record.extraction_status = "Approved"
        record.reviewed_by = reviewer
        record.review_notes = notes
        write(record)
        log("Approved contract written to GCS curated zone", contract_id=contract_id)

    return RedirectResponse(url="/queue", status_code=303)
