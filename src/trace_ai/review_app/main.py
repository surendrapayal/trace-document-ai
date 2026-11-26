from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from trace_ai.review_app.routes.queue import router as queue_router
from trace_ai.review_app.routes.review import router as review_router
from trace_ai.review_app.routes.contracts import router as contracts_router
from trace_ai.review_app.routes.decisions import router as decisions_router
from trace_ai.review_app.routes.pipeline import router as pipeline_router

app = FastAPI(title="TRACE Review App")

app.include_router(queue_router)
app.include_router(review_router)
app.include_router(contracts_router)
app.include_router(decisions_router)
app.include_router(pipeline_router)


@app.get("/")
async def root():
    return RedirectResponse(url="/queue")
