"""Removal from the early-bird list (unsubscribe): `early_bird_unsubscribe`.

One more function on `early_bird_signups` (0009), with the same conventions: a definer with a fixed
`search_path`, argument validation, no rights for PUBLIC, EXECUTE for the app role.

- `early_bird_unsubscribe` deletes the row with that ID, pending or confirmed, and returns its language;
  null when there is no such row (already removed, or pruned). Nothing is kept about a removed address.

The api calls it only after it has checked the removal link's MAC over the same ID
(`changelens/api/early_bird_unsubscribe.py`), so the ID alone removes nothing through the api. Like the other
four functions it returns no address. The downgrade drops the function; removed rows stay removed.

Reading the list (addresses, for a mail to it) is not a function: the owner role reads the table directly
(`python -m changelens.early_bird_export`), and the app role still has no way to read an address.

Revision ID: 0010_early_bird_unsubscribe
Revises: 0009_early_bird
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010_early_bird_unsubscribe"
down_revision: Union[str, Sequence[str], None] = "0009_early_bird"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
_HEADER = "LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$"
_INVALID = "RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';"

FUNCTIONS = {
    "early_bird_unsubscribe(uuid)": f"""
CREATE FUNCTION early_bird_unsubscribe(p_id uuid) RETURNS text
{_HEADER}
DECLARE
    v_locale text;
BEGIN
    IF p_id IS NULL THEN
        {_INVALID}
    END IF;
    DELETE FROM public.early_bird_signups s WHERE s.id = p_id RETURNING s.locale::text INTO v_locale;
    RETURN v_locale;
END
$$""",
}


def upgrade() -> None:
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
