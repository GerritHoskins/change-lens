"""Dismissal reason on review events (WP-C, owner decision 2026-11-16).

`review_events.dismissal_reason`: why the user dismissed a finding, one of `reworded`, `wrong_passage`,
`irrelevant` or `other`. The API requires it on new dismissals and refuses it on every other action, with
no default. Dismissals recorded before this revision keep a null reason. The column holds a fixed code,
never document content. `review_events` keeps its RLS policy and grants from 0003.

Revision ID: 0007_dismissal_reason
Revises: 0006_social_sign_in
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_dismissal_reason"
down_revision: Union[str, Sequence[str], None] = "0006_social_sign_in"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("review_events", sa.Column("dismissal_reason", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_review_dismissal_reason", "review_events",
        "dismissal_reason IS NULL OR (action = 'dismissed' AND dismissal_reason IN "
        "('reworded', 'wrong_passage', 'irrelevant', 'other'))")


def downgrade() -> None:
    op.drop_constraint("ck_review_dismissal_reason", "review_events", type_="check")
    op.drop_column("review_events", "dismissal_reason")
