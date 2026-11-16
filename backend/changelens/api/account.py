"""`DELETE /me` (03 §9.4, 03a P8 DELETE_ACCOUNT; I-8 S5): in-app account deletion (Apple 5.1.1(v)).

Under GUARD, no body. Freezes the account first, so every later request with the same token is
`unauthenticated`, then runs the remaining steps in the request. `204` when everything finished, `202`
when a step is still pending (maintenance completes it). The app treats both as signed out.
`DELETE /team` is not built: v1 has no teams.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from changelens.api.auth import current_principal
from changelens.domain.accounts import process_account_deletion, request_account_deletion
from changelens.domain.identity import Principal

router = APIRouter()


@router.delete("/me", status_code=204, responses={202: {"description": "Deletion pending; signed out"}})
def delete_account(request: Request, principal: Principal = Depends(current_principal)):
    state = request.app.state
    request_account_deletion(state.db, principal)
    done = process_account_deletion(state.db, state.store, state.idp, principal.tenant_id, principal.user_id,
                                    apple=state.apple)
    return Response(status_code=204 if done else 202)
