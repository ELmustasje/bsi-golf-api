import datetime
from spond import spond

from utils.extractors import (
    extract_attendees_name,
    extract_events_in_range,
    extract_future_events,
)
from utils.creators import create_member_dict

from utils.filters import filter_events

username = "+4748456975"
password = "TB-bt1a@"
group_id = "8D0C460783EB466B98AF0C3980163A34"


async def get_next_training_attendees():
    s = spond.Spond(username=username, password=password)
    now = datetime.datetime.now(datetime.timezone.utc)
    end = now + datetime.timedelta(days=6)

    future_events = await extract_events_in_range(now, end, s, group_id)

    future_trainings = filter_events(future_events, "heading", "Trening")
    members = await create_member_dict(s, group_id)
    return extract_attendees_name(future_trainings[0], members)
