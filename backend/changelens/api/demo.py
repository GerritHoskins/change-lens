"""The demo period (docs/demo-wall-handoff.md): the limit's state and the feedback form.

`GET /me/demo` returns the account's state; `POST /session` carries the same object as `demo`:

    {"limit": 3, "used": 2, "in_flight": 0, "remaining": 1,
     "feedback": {"submitted": false, "discount_offered": false}}

`remaining` is `max(0, limit - used - in_flight)`. With the limit off (`CHANGELENS_DEMO_COMPARISON_LIMIT=0`)
`limit` and `remaining` are null and the app shows no demo line and no wall. `discount_offered` is the
`CHANGELENS_DEMO_FEEDBACK_DISCOUNT` setting: it switches one sentence on in the app and nothing here.

`POST /me/demo-feedback` stores the account's one answer (`201`, the new state); a second one is
`409 already_answered`. Feedback never changes the limit. The two text fields hold whatever the person typed:
control characters are removed (line breaks stay), the ends are trimmed, and the text is stored as written
otherwise. It is never logged, counted or echoed: validation errors name fields only (`api/errors.py`).
"""
from __future__ import annotations

import unicodedata
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, StrictStr, field_validator, model_validator

from changelens.api.auth import current_principal
from changelens.api.errors import ApiError
from changelens.domain.identity import Principal

router = APIRouter()
OTHER_MIN, TEXT_MAX = 20, 500
Missing = Literal["screenshot_import", "more_file_types", "share_report", "better_accuracy", "faster_results",
                  "team", "other"]
Price = Literal["eur_0", "eur_5", "eur_10", "eur_15", "eur_over_15", "not_sure"]


def clean_text(value: Optional[str]) -> Optional[str]:
    """Control characters removed (a line break is kept as `\\n`), and lone surrogates, which the database
    can't store; ends trimmed. Empty after that is no text. Nothing else is changed, nothing judges it."""
    if value is None:
        return None
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    kept = "".join(c for c in value if c == "\n" or unicodedata.category(c) not in ("Cc", "Cs"))
    return kept.strip() or None


class DemoFeedbackIn(BaseModel):
    """`missing` and `price` are required codes. `missing_other` is required text (20 to 500 characters)
    exactly when `missing` is `other`, and must be null or absent otherwise. `anything_else` is optional."""
    model_config = ConfigDict(extra="forbid")
    missing: Missing
    missing_other: Optional[StrictStr] = None
    anything_else: Optional[StrictStr] = None
    price: Price

    @field_validator("missing_other", "anything_else")
    @classmethod
    def _text(cls, value):
        value = clean_text(value)
        if value is not None and len(value) > TEXT_MAX:
            raise ValueError("too long")
        return value

    @model_validator(mode="after")
    def _other(self):
        if self.missing == "other":
            if self.missing_other is None or len(self.missing_other) < OTHER_MIN:
                raise ValueError("missing_other needs at least %d characters" % OTHER_MIN)
        elif "missing_other" in self.model_fields_set and self.missing_other is not None:
            raise ValueError("missing_other belongs to the answer other")
        return self


def demo_state(repo, settings, account_id) -> dict:
    used, in_flight = repo.demo_counts()
    limit = settings.demo_comparison_limit or None
    return {"limit": limit, "used": used, "in_flight": in_flight,
            "remaining": None if limit is None else max(0, limit - used - in_flight),
            "feedback": {"submitted": repo.demo_feedback(account_id) is not None,
                         "discount_offered": settings.demo_feedback_discount}}


def check_demo_limit(repo, settings) -> None:
    """Admission for a new comparison, inside its transaction. Under the tenant's demo lock, so two
    simultaneous starts are checked one after the other; completed and in-flight comparisons both hold a
    place. `403`, not `429`: waiting does not help. With the limit off nothing is locked or read."""
    limit = settings.demo_comparison_limit
    if not limit:
        return
    repo.lock_demo()
    used, in_flight = repo.demo_counts()
    if used + in_flight >= limit:
        raise ApiError(403, "demo_limit_reached", "the demo comparisons of this account are used",
                       extra={"used": used, "in_flight": in_flight, "limit": limit})


@router.get("/me/demo")
def get_demo(request: Request, principal: Principal = Depends(current_principal)):
    state = request.app.state
    with state.db.tenant_scope(principal.tenant_id) as repo:
        return demo_state(repo, state.settings, principal.user_id)


@router.post("/me/demo-feedback", status_code=201)
def post_demo_feedback(body: DemoFeedbackIn, request: Request, principal: Principal = Depends(current_principal)):
    state = request.app.state
    with state.db.tenant_scope(principal.tenant_id) as repo:
        if not repo.record_demo_feedback(principal.user_id, missing=body.missing, missing_other=body.missing_other,
                                         anything_else=body.anything_else, price=body.price):
            raise ApiError(409, "already_answered", "this account has already sent its feedback")
        return demo_state(repo, state.settings, principal.user_id)
