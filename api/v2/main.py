import logging
import random
from typing import Any, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from api.v2.data_store import store as data_store
from api.v2.utils.spond import (
    get_all_members,
    get_members_not_attending_next_event,
    get_next_training_attendees,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Restrict access to the production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bsi-golf-side.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------
# Models
# --------------------------
class Group(BaseModel):
    group_id: int
    members: List[Any]


class SwapRequest(BaseModel):
    attendee_one: str
    attendee_two: str


class ShuffleResponse(BaseModel):
    sim_count: int
    total_attendees: int
    groups: List[Group]


# --------------------------
# Helpers
# --------------------------
def shuffle_into_groups(
    attendees: List[Any], sim_count: int
) -> List[List[Any]]:
    # Randomize order
    pool = attendees[:]  # copy to avoid mutating original
    random.shuffle(pool)

    # Balanced round-robin distribution after shuffle
    groups: List[List[Any]] = [[] for _ in range(sim_count)]
    for idx, person in enumerate(pool):
        groups[idx % sim_count].append(person)
    return groups


def normalise_member_name(member: Any) -> Optional[str]:
    """Return a trimmed string representation for a member entry."""

    if isinstance(member, str):
        return member.strip()
    if isinstance(member, dict):
        for key in ("name", "full_name", "fullName", "displayName"):
            value = member.get(key)
            if isinstance(value, str):
                return value.strip()
    return None


def find_member_position(
    groups: List[Any], attendee: str
) -> Optional[Tuple[int, int]]:
    """Locate the (group_index, member_index) pair for an attendee name."""

    target = attendee.strip().casefold()
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue

        members = group.get("members", [])
        if not isinstance(members, list):
            continue

        for member_index, member in enumerate(members):
            name = normalise_member_name(member)
            if name and name.casefold() == target:
                return group_index, member_index
    return None


# --------------------------
# Routes
# --------------------------
@app.get("/attendeesFromSpond")
async def get_attendees_from_spond():
    attendees = await get_next_training_attendees()
    await data_store.replace_attendees(attendees)
    return JSONResponse(
        content=attendees,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/attendees/")
async def get_attendees():
    """Return the current attendees from the PostgreSQL store."""
    attendees = await data_store.get_attendees()
    return JSONResponse(
        content=attendees,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/members/")
async def get_members():
    """Return every member registered in the Spond group."""

    members = await get_all_members()
    return JSONResponse(
        content=members,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/members/notAttendingNextEvent")
async def get_members_not_attending():
    """Return members who are not attending the next upcoming training event."""

    members = await get_members_not_attending_next_event()
    return JSONResponse(
        content=members,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/groups/shuffle", response_model=ShuffleResponse)
async def post_shuffle_attendees(
    sim_count: int = Query(
        ..., ge=1, description="Number of simulators / groups to create"
    ),
):
    # Load attendees
    attendees = await data_store.get_attendees()

    # Compute groups
    groups_raw = shuffle_into_groups(attendees, sim_count)
    groups_model = [
        Group(group_id=i + 1, members=members) for i, members in enumerate(groups_raw)
    ]

    # Persist groups in the PostgreSQL store (same structure as response.groups)
    groups_payload = [g.model_dump() for g in groups_model]
    await data_store.replace_groups(groups_payload)

    # Return the same groups in a typed response
    return ShuffleResponse(
        sim_count=sim_count, total_attendees=len(attendees), groups=groups_model
    )


@app.post("/groups/swap", response_model=ShuffleResponse)
async def post_swap_attendees(payload: SwapRequest) -> ShuffleResponse:
    """Swap two attendees between groups and return the updated grouping."""

    groups_data = await data_store.get_groups()
    if not groups_data:
        raise HTTPException(
            status_code=404, detail="No groups available to modify."
        )

    first_pos = find_member_position(groups_data, payload.attendee_one)
    if first_pos is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find attendee '{payload.attendee_one}' in any group.",
        )

    second_pos = find_member_position(groups_data, payload.attendee_two)
    if second_pos is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find attendee '{payload.attendee_two}' in any group.",
        )

    group_a, member_a = first_pos
    group_b, member_b = second_pos

    groups_data[group_a]["members"][member_a], groups_data[group_b]["members"][member_b] = (
        groups_data[group_b]["members"][member_b],
        groups_data[group_a]["members"][member_a],
    )

    try:
        groups_model = [Group(**group) for group in groups_data]
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored group data is invalid after swap operation.",
        ) from exc

    await data_store.replace_groups([group.model_dump() for group in groups_model])

    total_attendees = sum(len(group.members) for group in groups_model)
    return ShuffleResponse(
        sim_count=len(groups_model),
        total_attendees=total_attendees,
        groups=groups_model,
    )


@app.get("/groups/", response_model=ShuffleResponse)
async def get_groups() -> JSONResponse:
    """Return the most recently saved groups from the PostgreSQL store."""

    groups = await data_store.get_groups()

    try:
        groups_model = [Group(**group) for group in groups]
    except ValidationError as exc:
        raise HTTPException(
            status_code=500, detail="Stored group data is invalid."
        ) from exc

    response_payload = ShuffleResponse(
        sim_count=len(groups_model),
        total_attendees=sum(len(group.members) for group in groups_model),
        groups=groups_model,
    )

    return JSONResponse(
        content=response_payload.model_dump(),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/")
async def root():
    return {"message": "API v2 is running!"}
