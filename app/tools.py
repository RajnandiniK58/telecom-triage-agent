from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def lookup_customer_profile(customer_id: str) -> dict[str, Any]:
    """Return a customer profile by customer ID (case-insensitive) from local mock data.

    Returns the matching record, or ``{"error": "Customer not found"}``.
    """
    target_id = customer_id.strip().upper()
    for customer in _load_json_data("customers.json"):
        if str(customer.get("customer_id", "")).upper() == target_id:
            return dict(customer)

    return {"error": "Customer not found"}


def lookup_network_status(city: str) -> dict[str, Any]:
    """Return network status details for a city (case-insensitive match)."""
    target_city = city.strip().lower()
    for record in _load_json_data("network.json"):
        if str(record.get("city", "")).strip().lower() == target_city:
            return dict(record)

    return {"error": "City not found"}


def lookup_knowledge(topic: str) -> dict[str, Any]:
    """Return a knowledge base article by topic (case-insensitive match)."""
    target_topic = topic.strip().lower()
    for record in _load_json_data("knowledge.json"):
        if str(record.get("topic", "")).strip().lower() == target_topic:
            return dict(record)

    return {"error": "Knowledge article not found"}


@lru_cache(maxsize=None)
def _load_json_data(filename: str) -> tuple[dict[str, Any], ...]:
    """Load records from a JSON file in app/data (cached; returned read-only)."""
    data_path = Path(__file__).resolve().parent / "data" / filename
    with data_path.open("r", encoding="utf-8") as file:
        return tuple(json.load(file))
