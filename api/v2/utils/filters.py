def filter_events(events, field, filter):
    filterd = []
    for event in events:
        if filter.lower() in event[field].lower():
            filterd.append(event)
    return filterd
