"""Test-only: give a demo account one of the old finance personas as its own money data.

The app never serves a persona (an account without its own data gets has_data=false or 409 no_finance_data).
Tests that need a full year of realistic data call `seed_persona` explicitly. It stores the persona snapshot
as the account's own data, the same way a statement import does.
"""

from __future__ import annotations

from lifeline_data.finance import DEMO_PERSONA_ID, demo_subject, fixture_snapshot


async def seed_persona(device_id: str, persona_id: str = DEMO_PERSONA_ID) -> str:
    """Store persona `persona_id` as the own data of the demo account for `device_id`. Returns the subject.

    Call it after the in-process app started (inside the `client` fixture) and after `POST /v1/auth/demo`.
    """
    from lifeline_api import money
    from lifeline_api.main import app

    sub = demo_subject(device_id)
    await money.save_snapshot(app.state.lifeline, sub, fixture_snapshot(f"persona:{persona_id}"))
    return sub
