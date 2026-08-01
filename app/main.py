from fastapi import FastAPI, HTTPException

from app.agent import run_triage
from app.schemas import TriageRequest

app = FastAPI(
    title="Telecom Triage Agent",
    description="AI Agent for Telecom Support Ticket Triage",
    version="1.0.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Telecom Triage Agent is running!"}


@app.post("/triage")
def triage(request: TriageRequest) -> dict:
    """Run telecom support ticket triage for a customer complaint."""
    try:
        return run_triage(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
