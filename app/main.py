from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.workflows import router as workflows_router
from .routers.assistant import router as assistant_router

app = FastAPI(title="Workflow Builder API", version="0.1.0")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(workflows_router, prefix="/api")
app.include_router(assistant_router)


@app.get("/health")
async def health():
	return {"status": "ok"}
