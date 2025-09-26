from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, List


ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


async def extract_future_events(s, group_id: str) -> List[Dict[str, Any]]:
    """Return events ending within the last 48 hours or in the future."""

    events: Iterable[Dict[str, Any]] = await s.get_events([group_id])
    fut_events: List[Dict[str, Any]] = []

    now = datetime.datetime.now(datetime.timezone.utc)
    threshold = now - datetime.timedelta(hours=48)

    for event in events:
        end_timestamp = event.get("endTimestamp")
        if not end_timestamp:
            continue

        try:
            event_dt = datetime.datetime.strptime(end_timestamp, ISO_FORMAT)
            event_dt = event_dt.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue

        if event_dt > threshold:
            fut_events.append(event)

    return fut_events


async def extract_events_in_range(
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    s,
    group_id: str,
) -> List[Dict[str, Any]]:
    """Return events that end inside the inclusive ``start_time``/``end_time`` window."""

    events: Iterable[Dict[str, Any]] = await s.get_events([group_id])
    in_range_events: List[Dict[str, Any]] = []

    for event in events:
        end_timestamp = event.get("endTimestamp")
        if not end_timestamp:
            continue

        try:
            event_dt = datetime.datetime.strptime(end_timestamp, ISO_FORMAT)
            event_dt = event_dt.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue

        if start_time <= event_dt <= end_time:
            in_range_events.append(event)

    return in_range_events


def extract_attendees_id(event: Dict[str, Any]) -> List[str]:
    """Return the attendee ids that accepted the event invitation."""

    responses = event.get("responses", {})
    accepted: Iterable[str] = responses.get("acceptedIds", [])
    return [attendee_id for attendee_id in accepted if isinstance(attendee_id, str)]


def extract_attendees_name(event: Dict[str, Any], members_dict: Dict[str, str]) -> List[str]:
    """Map attendee ids in an event to their names using ``members_dict``."""

    attendee_ids = extract_attendees_id(event)
    return [members_dict.get(attendee_id, attendee_id) for attendee_id in attendee_ids]
