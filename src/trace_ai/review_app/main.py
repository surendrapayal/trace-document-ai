from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from trace_ai.review_app.routes.queue import router as queue_router
from trace_ai.review_app.routes.review import router as review_router

app = FastAPI(title="TRACE Review App")

app.include_router(queue_router)
app.include_router(review_router)


@app.get("/")
async def root():
    return RedirectResponse(url="/queue")
