from typing import Iterable, List, Dict, Any


def filter_events(
    events: Iterable[Dict[str, Any]], field: str, value: str
) -> List[Dict[str, Any]]:
    """Filter events where ``value`` appears in ``field`` (case-insensitive)."""

    filtered: List[Dict[str, Any]] = []
    target = value.lower()

    for event in events:
        candidate = event.get(field)
        if isinstance(candidate, str) and target in candidate.lower():
            filtered.append(event)

    return filtered
