from typing import Dict, Any


async def create_member_dict(s, group_id: str) -> Dict[str, str]:
    """Return a mapping of member id to full name for a given Spond group."""

    group: Dict[str, Any] = await s.get_group(group_id)
    members: Dict[str, str] = {}

    for member in group.get("members", []):
        member_id = member.get("id")
        first = member.get("firstName", "").strip()
        last = member.get("lastName", "").strip()

        if not member_id:
            continue

        full_name = " ".join(part for part in (first, last) if part)
        members[member_id] = full_name or member_id

    return members
