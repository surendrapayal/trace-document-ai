from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from trace_ai.delivery.storage_backend import get_pending_review
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/queue", response_class=HTMLResponse)
async def queue(request: Request):
    contracts = get_pending_review()
    contracts.sort(key=lambda c: c.get("extracted_at", ""), reverse=True)
    return templates.TemplateResponse("queue.html", {"request": request, "contracts": contracts})
