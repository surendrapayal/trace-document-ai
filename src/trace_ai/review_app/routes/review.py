from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from trace_ai.delivery.storage_backend import get_contract, update_review_decision
from trace_ai.delivery.gcs_writer import write
from trace_ai.normalization.schema import ContractRecord
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/review/{contract_id}", response_class=HTMLResponse)
async def review_detail(request: Request, contract_id: str):
    data = get_contract(contract_id)
    if not data:
        raise HTTPException(status_code=404, detail="Contract not found")
    return templates.TemplateResponse("review.html", {"request": request, "contract": data})


@router.post("/review/{contract_id}")
async def submit_review(
    contract_id: str,
    reviewer: str = Form(...),
    decision: str = Form(...),
    notes: str = Form(default=""),
):
    if decision not in ("Approved", "Rejected"):
        raise HTTPException(status_code=400, detail="Decision must be Approved or Rejected")

    data = get_contract(contract_id)
    if not data:
        raise HTTPException(status_code=404, detail="Contract not found")

    update_review_decision(contract_id, reviewer, decision, notes)

    if decision == "Approved":
        record = ContractRecord(**data)
        record.extraction_status = "Approved"
        record.reviewed_by = reviewer
        record.review_notes = notes
        write(record)

    return RedirectResponse(url="/queue", status_code=303)
