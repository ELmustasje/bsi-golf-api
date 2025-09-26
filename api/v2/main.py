import logging
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from asyncio import Lock
from pydantic import BaseModel, ValidationError
from typing import Any, List, Optional, Tuple
import json
import os
import random
from pathlib import Path

from api.v2.utils.spond import get_next_training_attendees

logging.basicConfig(level=logging.INFO)

app = FastAPI()

MODULE_DIR = Path(__file__).resolve().parent
RUNTIME_DATA_DIR = Path(os.getenv("BSI_RUNTIME_DATA_DIR", "/tmp/bsi-golf-api"))

ATTENDEES_PATH = RUNTIME_DATA_DIR / "attendees.json"
GROUPS_PATH = RUNTIME_DATA_DIR / "groups.json"

ATTENDEES_SEED_PATH = MODULE_DIR / "attendees.json"
GROUPS_SEED_PATH = MODULE_DIR / "groups.json"

# Restrict access to the production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bsi-golf-side.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

lock = Lock()


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
async def load_json_array(
    path: Path, kind: str, *, seed_path: Optional[Path] = None
) -> List[Any]:
    candidates = [path]
    if seed_path and seed_path not in candidates:
        candidates.append(seed_path)

    selected_path: Optional[Path] = None
    for candidate in candidates:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            selected_path = candidate_path
            break

    if selected_path is None:
        locations = ", ".join(str(Path(c)) for c in candidates)
        raise HTTPException(
            status_code=500,
            detail=f"{kind} file not found in any of: {locations}",
        )
    try:
        async with lock:
            with selected_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, list):
            raise HTTPException(
                status_code=500,
                detail=f"{os.path.basename(
                    selected_path)} must be a JSON array (list).",
            )
        return data
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in {os.path.basename(selected_path)}: {e}"
        )


async def save_json(path: Path, payload: Any) -> None:
    async with lock:
        # Ensure dir exists
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


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
    await save_json(ATTENDEES_PATH, attendees)
    return JSONResponse(
        content=attendees,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/attendees/")
async def get_attendees():
    """Reads the attendees from a file and returns them."""
    attendees = await load_json_array(
        ATTENDEES_PATH, "Attendees", seed_path=ATTENDEES_SEED_PATH
    )
    return JSONResponse(
        content=attendees,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/groups/shuffle", response_model=ShuffleResponse)
async def post_shuffle_attendees(
    sim_count: int = Query(
        ..., ge=1, description="Number of simulators / groups to create"
    ),
):
    # Load attendees
    attendees = await load_json_array(
        ATTENDEES_PATH, "Attendees", seed_path=ATTENDEES_SEED_PATH
    )

    # Compute groups
    groups_raw = shuffle_into_groups(attendees, sim_count)
    groups_model = [
        Group(group_id=i + 1, members=members) for i, members in enumerate(groups_raw)
    ]

    # Persist groups to groups.json (store plain JSON, same structure as response.groups)
    groups_payload = [g.model_dump() for g in groups_model]
    await save_json(GROUPS_PATH, groups_payload)

    # Return the same groups in a typed response
    return ShuffleResponse(
        sim_count=sim_count, total_attendees=len(attendees), groups=groups_model
    )


@app.post("/groups/swap", response_model=ShuffleResponse)
async def post_swap_attendees(payload: SwapRequest) -> ShuffleResponse:
    """Swap two attendees between groups and return the updated grouping."""

    groups_data = await load_json_array(
        GROUPS_PATH, "Groups", seed_path=GROUPS_SEED_PATH
    )
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

    await save_json(GROUPS_PATH, [group.model_dump() for group in groups_model])

    total_attendees = sum(len(group.members) for group in groups_model)
    return ShuffleResponse(
        sim_count=len(groups_model),
        total_attendees=total_attendees,
        groups=groups_model,
    )


@app.get("/groups/")
async def get_groups():
    """Reads the most recently saved groups from groups.json."""
    groups = await load_json_array(
        GROUPS_PATH, "Groups", seed_path=GROUPS_SEED_PATH
    )
    return JSONResponse(
        content=groups,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/")
async def root():
    return {"message": "API v2 is running!"}
