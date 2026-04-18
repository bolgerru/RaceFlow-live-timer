"""Deployed API origin for the sailing-event server.

Override with environment variable RACE_FLOW_API_BASE (e.g. https://teamracing.xyz).
When the timer runs on a different origin than the API, cookies from
POST /api/events/select are not sent on subsequent requests; use ?eventId= on
each event-scoped call (this client always passes eventId for those).
"""

from __future__ import annotations

import os

DEFAULT_API_BASE_URL = "https://teamracing.xyz"


def get_api_base_url() -> str:
    return os.environ.get("RACE_FLOW_API_BASE", DEFAULT_API_BASE_URL).rstrip("/")
