"""Events API: list and select sailing events (shared helpers for bootstrap + client)."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

import requests

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 15


class EventListItem(TypedDict, total=False):
    id: str
    name: str
    section: str
    startDate: str
    endDate: str


def parse_events_payload(data: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Parse GET /api/events JSON body. Expects { events: EventListItem[] }."""
    if not isinstance(data, dict):
        return [], "Invalid response: expected a JSON object."
    raw = data.get("events")
    if raw is None:
        return [], "Invalid response: missing \"events\" array."
    if not isinstance(raw, list):
        return [], "Invalid response: \"events\" must be an array."
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        eid = item.get("id")
        name = item.get("name")
        section = item.get("section")
        if eid is None or name is None or section is None:
            log.debug("Skipping event item missing id, name, or section: %s", item)
            continue
        normalized: dict[str, Any] = {
            "id": str(eid),
            "name": str(name),
            "section": str(section),
        }
        if item.get("startDate") is not None:
            normalized["startDate"] = str(item["startDate"])
        if item.get("endDate") is not None:
            normalized["endDate"] = str(item["endDate"])
        out.append(normalized)
    return out, None


def fetch_events(session: requests.Session, base_url: str) -> tuple[list[dict[str, Any]], str | None]:
    """GET /api/events. Uses session for cookies. Returns (events, error_message)."""
    url = f"{base_url.rstrip('/')}/api/events"
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT_S)
        if not resp.ok:
            return [], f"Could not load events (HTTP {resp.status_code})."
        data = resp.json()
    except requests.RequestException as exc:
        log.info("GET /api/events failed: %s", exc)
        return [], f"Could not load events: {exc}"
    except ValueError as exc:
        log.info("GET /api/events: invalid JSON: %s", exc)
        return [], "Could not load events: invalid response."
    events, parse_err = parse_events_payload(data)
    if parse_err:
        return [], parse_err
    return events, None


def select_event(session: requests.Session, base_url: str, event_id: str) -> str | None:
    """POST /api/events/select with { eventId }. Sets selected_event cookie on same-origin."""
    url = f"{base_url.rstrip('/')}/api/events/select"
    try:
        resp = session.post(
            url,
            json={"eventId": event_id},
            timeout=REQUEST_TIMEOUT_S,
        )
        if not resp.ok:
            return f"Could not select event (HTTP {resp.status_code})."
    except requests.RequestException as exc:
        log.info("POST /api/events/select failed: %s", exc)
        return f"Could not select event: {exc}"
    return None


def event_params(event_id: str) -> dict[str, str]:
    """Query parameters for event-scoped timer endpoints."""
    return {"eventId": str(event_id)}
