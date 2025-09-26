import datetime
from typing import List

from fastapi import HTTPException
from spond import spond

from api.v2.utils.creators import create_member_dict
from api.v2.utils.extractors import extract_attendees_name, extract_events_in_range
from api.v2.utils.filters import filter_events

username = "+4748456975"
password = "TB-bt1a@"
group_id = "8D0C460783EB466B98AF0C3980163A34"


async def get_next_training_attendees() -> List[str]:
    """Fetch accepted attendees for the next upcoming training session."""

    client = spond.Spond(username=username, password=password)
    now = datetime.datetime.now(datetime.timezone.utc)
    end = now + datetime.timedelta(days=6)

    future_events = await extract_events_in_range(now, end, client, group_id)
    future_trainings = filter_events(future_events, "heading", "Trening")

    if not future_trainings:
        raise HTTPException(status_code=404, detail="No upcoming training found in Spond.")

    members = await create_member_dict(client, group_id)
    return extract_attendees_name(future_trainings[0], members)
