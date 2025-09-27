import datetime
import os
from typing import List

from fastapi import HTTPException
from spond import spond

from api.v2.utils.creators import create_member_dict
from api.v2.utils.extractors import (
    extract_attendees_id,
    extract_attendees_name,
    extract_events_in_range,
)
from api.v2.utils.filters import filter_events

group_id = "8D0C460783EB466B98AF0C3980163A34"


def _get_credentials() -> tuple[str, str]:
    username = os.getenv("SPOND_USERNAME")
    password = os.getenv("SPOND_PASSWORD")

    if not username or not password:
        raise HTTPException(
            status_code=500,
            detail="Spond credentials are not configured.",
        )

    return username, password


async def get_next_training_attendees() -> List[str]:
    """Fetch accepted attendees for the next upcoming training session."""

    username, password = _get_credentials()
    client = spond.Spond(username=username, password=password)
    now = datetime.datetime.now(datetime.timezone.utc)
    end = now + datetime.timedelta(days=6)

    try:
        future_events = await extract_events_in_range(now, end, client, group_id)
        future_trainings = filter_events(future_events, "heading", "Trening")

        if not future_trainings:
            raise HTTPException(
                status_code=404, detail="No upcoming training found in Spond."
            )

        members = await create_member_dict(client, group_id)
        return extract_attendees_name(future_trainings[0], members)
    finally:
        await client.clientsession.close()


async def get_all_members() -> List[str]:
    """Return the full member list for the configured Spond group."""

    username, password = _get_credentials()
    client = spond.Spond(username=username, password=password)

    try:
        members = await create_member_dict(client, group_id)
        return sorted(members.values())
    finally:
        await client.clientsession.close()


async def get_members_not_attending_next_event() -> List[str]:
    """Return members who are not attending the next upcoming training event."""

    username, password = _get_credentials()
    client = spond.Spond(username=username, password=password)
    now = datetime.datetime.now(datetime.timezone.utc)
    end = now + datetime.timedelta(days=6)

    try:
        future_events = await extract_events_in_range(now, end, client, group_id)
        future_trainings = filter_events(future_events, "heading", "Trening")

        if not future_trainings:
            raise HTTPException(
                status_code=404, detail="No upcoming training found in Spond."
            )

        members = await create_member_dict(client, group_id)
        attendees_ids = set(extract_attendees_id(future_trainings[0]))

        non_attending = [
            name for member_id, name in members.items() if member_id not in attendees_ids
        ]
        return sorted(non_attending)
    finally:
        await client.clientsession.close()
