"""API tests. The LLM call is patched, so these run offline and free."""

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.llm import LLMConfigError
from app.main import app
from app.schemas import Category, Priority, ToolName, TriageDecision

client = TestClient(app)

PAYLOAD = {
    "customer_id": "CUST1001",
    "message": "Network problem since 2 days",
    "location": "Mumbai",
}


def make_decision(**overrides) -> TriageDecision:
    data = dict(
        category=Category.NETWORK_ISSUES,
        priority=Priority.P0,
        next_tool=ToolName.NETWORK_STATUS,
        reasoning="Prolonged loss of connectivity.",
        why="Outage-like complaint; check city network status.",
    )
    data.update(overrides)
    return TriageDecision(**data)


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def _fake(request):
        calls.append(request)
        return make_decision()

    monkeypatch.setattr(agent, "_invoke_llm", _fake)
    return calls


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_triage_happy_path(fake_llm):
    resp = client.post("/triage", json=PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "Network Issues"
    assert body["priority"] == "P0"
    assert body["next_tool"] == "lookup_network_status"
    assert body["tool_result"]["city"] == "Mumbai"
    assert body["needs_human_review"] is False


def test_customer_id_is_normalised(fake_llm):
    resp = client.post("/triage", json={**PAYLOAD, "customer_id": " cust1001 "})
    assert resp.status_code == 200


def test_unknown_customer_returns_404_without_calling_llm(fake_llm):
    resp = client.post("/triage", json={**PAYLOAD, "customer_id": "CUST9999"})
    assert resp.status_code == 404
    assert fake_llm == []


@pytest.mark.parametrize(
    "bad",
    [
        {**PAYLOAD, "message": ""},
        {**PAYLOAD, "message": "  "},
        {**PAYLOAD, "customer_id": ""},
        {"customer_id": "CUST1001"},
    ],
)
def test_invalid_input_returns_422(fake_llm, bad):
    assert client.post("/triage", json=bad).status_code == 422


def test_network_tool_falls_back_to_customer_city(monkeypatch):
    monkeypatch.setattr(agent, "_invoke_llm", lambda r: make_decision())
    resp = client.post("/triage", json={**PAYLOAD, "location": ""})
    assert resp.json()["tool_result"]["city"] == "Mumbai"  # CUST1001 lives in Mumbai


def test_knowledge_tool_uses_category(monkeypatch):
    monkeypatch.setattr(
        agent,
        "_invoke_llm",
        lambda r: make_decision(
            category=Category.BILLING_ISSUES,
            priority=Priority.P1,
            next_tool=ToolName.KNOWLEDGE,
        ),
    )
    body = client.post("/triage", json=PAYLOAD).json()
    assert body["tool_result"]["topic"] == "Billing Issues"


def test_retry_succeeds_on_second_attempt(monkeypatch):
    attempts = {"n": 0}

    def flaky(request):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("transient")
        return make_decision()

    monkeypatch.setattr(agent, "_invoke_llm", flaky)
    body = client.post("/triage", json=PAYLOAD).json()
    assert attempts["n"] == 2
    assert body["needs_human_review"] is False


def test_fallback_when_llm_keeps_failing(monkeypatch):
    def boom(request):
        raise RuntimeError("model down")

    monkeypatch.setattr(agent, "_invoke_llm", boom)
    resp = client.post("/triage", json=PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_human_review"] is True
    assert body["priority"] == "P1"
    assert body["tool_result"]["customer_id"] == "CUST1001"


def test_missing_api_key_returns_503(monkeypatch):
    def not_configured(request):
        raise LLMConfigError("GEMINI_API_KEY is not set")

    monkeypatch.setattr(agent, "_invoke_llm", not_configured)
    assert client.post("/triage", json=PAYLOAD).status_code == 503


def test_unexpected_error_returns_500_without_internals(monkeypatch):
    def broken(request, *a, **k):
        raise KeyError("secret-internal-detail")

    monkeypatch.setattr(agent, "_decide", broken)
    resp = client.post("/triage", json=PAYLOAD)
    assert resp.status_code == 500
    assert "secret-internal-detail" not in resp.text
