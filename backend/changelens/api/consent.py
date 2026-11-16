"""Usage-events consent (D-18 tier B; docs/api-contracts-draft.md C1).

Tier B is opt-in, off by default (§ 25 TDDDG, docs/legal/README.md). Each answer is an append-only row with
the choice, the time and the privacy-policy version it was given for. An answer for an older policy version
reads as unanswered, so the app asks again. Withdrawal is the same PUT with `false`.
"""
from __future__ import annotations

from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from changelens.api.auth import current_principal
from changelens.api.errors import ApiError
from changelens.domain.identity import Principal
from changelens.domain.models import ConsentEvent

router = APIRouter()
USAGE_EVENTS = "usage_events"


class UsageEventsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted: StrictBool
    policy_version: StrictStr = Field(min_length=1, max_length=32)


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usage_events: UsageEventsIn


def consent_state(row: Optional[ConsentEvent], current_version: str) -> dict:
    """The account's answer for the current policy version; an older version's answer counts as none."""
    if row is None or row.policy_version != current_version:
        return {"usage_events": {"granted": None, "policy_version": current_version, "decided_at": None}}
    decided = row.decided_at if row.decided_at.tzinfo else row.decided_at.replace(tzinfo=timezone.utc)
    return {"usage_events": {"granted": row.granted, "policy_version": row.policy_version,
                             "decided_at": decided.isoformat()}}


@router.get("/me/consent")
def get_consent(request: Request, principal: Principal = Depends(current_principal)):
    current = request.app.state.settings.consent_policy_version
    with request.app.state.db.tenant_scope(principal.tenant_id) as repo:
        return consent_state(repo.consent(principal.user_id, USAGE_EVENTS), current)


@router.put("/me/consent")
def put_consent(body: ConsentIn, request: Request, principal: Principal = Depends(current_principal)):
    current = request.app.state.settings.consent_policy_version
    if body.usage_events.policy_version != current:
        raise ApiError(409, "policy_version_stale", "re-read the consent text and answer again")
    with request.app.state.db.tenant_scope(principal.tenant_id) as repo:
        row = repo.record_consent(principal.user_id, USAGE_EVENTS, body.usage_events.granted, current)
        return consent_state(row, current)
