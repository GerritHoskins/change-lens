"""Account onboarding state (O-23): whether onboarding was completed and the last step reached.

The account is the dev-token tenant until I-8, because v1 has one tenant per account. I-8 swaps
`current_tenant` for GUARD and takes the account ID from `User.id`. The replay ("How ChangeLens
works") never calls these routes. The server doesn't know the step count: the app clamps.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from changelens.api.auth import current_tenant
from changelens.domain.models import AccountOnboarding

router = APIRouter()
MAX_STEP = 32  # sanity bound, not the design's step count


class OnboardingIn(BaseModel):
    """Exactly one of `{"step": n}` (1 ≤ n ≤ 32) or `{"completed": true}`."""
    model_config = ConfigDict(extra="forbid")
    step: Optional[StrictInt] = Field(default=None, ge=1, le=MAX_STEP)
    completed: Optional[StrictBool] = None

    @model_validator(mode="after")
    def _exactly_one(self):
        if len(self.model_fields_set) != 1 or not (self.step is not None or self.completed is True):
            raise ValueError("send exactly one of step or completed: true")
        return self


def _account(tenant: uuid.UUID) -> uuid.UUID:
    return tenant  # until I-8: one tenant per account, so the account ID is the tenant ID


def _state(row: Optional[AccountOnboarding]) -> dict:
    if row is None:
        return {"completed": False, "step": None}
    if row.onboarding_completed_at is not None:
        return {"completed": True, "step": None}
    return {"completed": False, "step": row.onboarding_step}


@router.get("/me/onboarding")
def get_onboarding(request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        return _state(repo.onboarding(_account(tenant)))


@router.put("/me/onboarding")
def put_onboarding(body: OnboardingIn, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        row = repo.record_onboarding(_account(tenant), step=body.step, completed=body.completed is True)
        return _state(row)
