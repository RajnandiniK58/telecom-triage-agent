import logging

from fastapi import FastAPI, HTTPException

from app.agent import CustomerNotFoundError, run_triage
from app.llm import LLMConfigError
from app.schemas import TriageRequest, TriageResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("triage.api")

app = FastAPI(
    title="Telecom Triage Agent",
    description="AI Agent for Telecom Support Ticket Triage",
    version="1.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Telecom Triage Agent is running!"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
def triage(request: TriageRequest) -> TriageResponse:
    """Run telecom support ticket triage for a customer complaint."""
    try:
        return run_triage(request)
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Customer '{request.customer_id}' not found."
        )
    except LLMConfigError:
        logger.error("LLM is not configured (missing GEMINI_API_KEY?)")
        raise HTTPException(
            status_code=503, detail="Triage service is not configured. Contact the administrator."
        )
    except Exception:
        # Log the details server-side; don't leak internals to the client.
        logger.exception("Unhandled error while triaging")
        raise HTTPException(status_code=500, detail="Internal error while triaging the ticket.")
