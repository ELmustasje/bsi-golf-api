import logging
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from asyncio import Lock
from pydantic import BaseModel
from typing import Any, List, Dict
import json
import os
import random

from api.v2.utils.spond import get_next_training_attendees

logging.basicConfig(level=logging.INFO)

app = FastAPI()

ATTENDEES_PATH = "./api/v2/attendees.json"
GROUPS_PATH = "./api/v2/groups.json"

# Allow all origins, methods, and headers (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

lock = Lock()


# --------------------------
# Models
# --------------------------
class Group(BaseModel):
    group_id: int
    members: List[Dict[str, Any]]


class ShuffleResponse(BaseModel):
    sim_count: int
    total_attendees: int
    groups: List[Group]


# --------------------------
# Helpers
# --------------------------
async def load_json_array(path: str, kind: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise HTTPException(status_code=500, detail=f"{
                            kind} file not found: {path}")
    try:
        async with lock:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, list):
            raise HTTPException(
                status_code=500,
                detail=f"{os.path.basename(
                    path)} must be a JSON array (list).",
            )
        return data
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, detail=f"Invalid JSON in {os.path.basename(path)}: {e}"
        )


async def save_json(path: str, payload: Any) -> None:
    async with lock:
        # Ensure dir exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def shuffle_into_groups(
    attendees: List[Dict[str, Any]], sim_count: int
) -> List[List[Dict[str, Any]]]:
    # Randomize order
    pool = attendees[:]  # copy to avoid mutating original
    random.shuffle(pool)

    # Balanced round-robin distribution after shuffle
    groups: List[List[Dict[str, Any]]] = [[] for _ in range(sim_count)]
    for idx, person in enumerate(pool):
        groups[idx % sim_count].append(person)
    return groups


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
    attendees = await load_json_array(ATTENDEES_PATH, "Attendees")
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
    attendees = await load_json_array(ATTENDEES_PATH, "Attendees")

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


@app.get("/groups/")
async def get_groups():
    """Reads the most recently saved groups from groups.json."""
    groups = await load_json_array(GROUPS_PATH, "Groups")
    return JSONResponse(
        content=groups,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/")
async def root():
    return {"message": "API v2 is running!"}
