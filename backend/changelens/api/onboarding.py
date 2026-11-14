"""Account onboarding state (O-23): whether onboarding was completed and the last step reached.

The account ID is the signed-in user's ID (`Principal.user_id`, I-8 S1); the row also carries the
tenant from the active membership, because v1 has one tenant per account. The replay ("How ChangeLens
works") never calls these routes. The server doesn't know the step count: the app clamps.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from changelens.api.auth import current_principal
from changelens.domain.identity import Principal
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


def _state(row: Optional[AccountOnboarding]) -> dict:
    if row is None:
        return {"completed": False, "step": None}
    if row.onboarding_completed_at is not None:
        return {"completed": True, "step": None}
    return {"completed": False, "step": row.onboarding_step}


@router.get("/me/onboarding")
def get_onboarding(request: Request, principal: Principal = Depends(current_principal)):
    with request.app.state.db.tenant_scope(principal.tenant_id) as repo:
        return _state(repo.onboarding(principal.user_id))


@router.put("/me/onboarding")
def put_onboarding(body: OnboardingIn, request: Request, principal: Principal = Depends(current_principal)):
    with request.app.state.db.tenant_scope(principal.tenant_id) as repo:
        row = repo.record_onboarding(principal.user_id, step=body.step, completed=body.completed is True)
        return _state(row)
