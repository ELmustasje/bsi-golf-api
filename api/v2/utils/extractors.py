import datetime


async def extract_future_events(s, group_id):
    events = await s.get_events([group_id])
    fut_events = []
    now = datetime.datetime.now()
    threshold = now - datetime.timedelta(hours=48)
    for event in events:
        endTimeStamp = event["endTimestamp"]
        formatString = "%Y-%m-%dT%H:%M:%SZ"
        date_time_object = datetime.datetime.strptime(
            endTimeStamp, formatString)

        if date_time_object > threshold:
            fut_events.append(event)

    return fut_events


async def extract_events_in_range(startTime, endTime, s, group_id):
    # Fetch events for the group
    events = await s.get_events([group_id])
    in_range_events = []

    # Expected format: 2025-09-24T10:00:00Z
    formatString = "%Y-%m-%dT%H:%M:%SZ"

    for event in events:
        endTimeStamp = event.get("endTimestamp")
        if not endTimeStamp:
            continue

        try:
            event_dt = datetime.datetime.strptime(endTimeStamp, formatString)
            event_dt = event_dt.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            # Skip malformed timestamps
            continue

        # Keep only events within the desired interval
        if startTime <= event_dt <= endTime:
            in_range_events.append(event)

    return in_range_events


def extract_attendees_id(event):
    attendees = []
    for id in event["responses"]["acceptedIds"]:
        attendees.append(id)

    return attendees


def extract_attendees_name(event, memebersDict):
    attendees = []
    for id in event["responses"]["acceptedIds"]:
        attendees.append(memebersDict[id])
    return attendees
