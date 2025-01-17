from fastapi import FastAPI, HTTPException
import asyncio
import random
from spond import spond
import datetime

# FastAPI instance
app = FastAPI()

# Credentials
username = "+4748456975"
password = "TB-bt1a@"
group_id = "8D0C460783EB466B98AF0C3980163A34"


# Helper Functions
async def get_all_members(next_training):
    member_dict = {}
    try:
        members_data = next_training["recipients"]["group"]["members"]
        for member in members_data:
            member_dict[member["id"]] = (
                member["firstName"],
                member["lastName"],
            )
    except KeyError as e:
        print(f"Error accessing members data: {e}")
    return member_dict


async def get_flex_attendiance(next_training):
    attending = next_training.get("responses", {}).get("acceptedIds", [])
    return attending


async def get_flex_memebers(next_training):
    attending = next_training.get("responses", {}).get("acceptedIds", [])
    declined = next_training.get("responses", {}).get("declinedIds", [])
    unanswered = next_training.get("responses", {}).get("unansweredIds", [])
    waitinglist = next_training.get("responses", {}).get("waitinglistIds", [])
    unconfirmed = next_training.get("responses", {}).get("unconfirmedIds", [])
    return attending + declined + unanswered + waitinglist + unconfirmed


async def get_fixed_members(next_training):
    member_dict = await get_all_members(next_training)
    flex_list = await get_flex_memebers(next_training)
    players = [member for member in member_dict.keys()
               if member not in flex_list]
    return players


async def all_attendies(next_training):
    fixed_members = await get_fixed_members(next_training)
    flex_members = await get_flex_attendiance(next_training)
    members_dict = await get_all_members(next_training)
    players = [
        members_dict[id] for id in fixed_members + flex_members if id in members_dict
    ]
    return players


async def split_into_random(sim_amount, attendies):
    if sim_amount <= 0:
        raise ValueError("sim_amount must be greater than 0.")
    if not attendies:
        raise ValueError("attendies list cannot be empty.")

    random.shuffle(attendies)
    groups = [[] for _ in range(sim_amount)]
    for i, attendee in enumerate(attendies):
        groups[i % sim_amount].append(attendee)

    return groups


# Routes
@app.get("/")
async def root():
    return {"message": "Spond API is running!"}


@app.get("/generate-random-groups/")
async def generate_random_groups(sim_amount: int):
    # Initialize Spond session
    s = spond.Spond(username=username, password=password)

    # Fetch events
    today = datetime.datetime.now()
    events = await s.get_events(group_id=group_id, min_start=today)

    if not events:
        raise HTTPException(
            status_code=404, detail="No upcoming events found.")

    next_training = events[0]
    attendies = await all_attendies(next_training)
    groups = await split_into_random(sim_amount, attendies)

    # Store the groups for later retrieval
    app.state.groups = groups

    return {"groups": groups}
