import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from asyncio import Lock
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
from spond import spond
import datetime
from dotenv import load_dotenv
import os

#
# Set up logging to print to terminal
logging.basicConfig(level=logging.INFO)
# Load environment variables in local development
if os.getenv("VERCEL_ENV") is None:  # VERCEL_ENV is automatically set in production
    load_dotenv()

# FastAPI instance
app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    # Replace "*" with specific domains for better security
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Credentials from environment variables
username = os.getenv("SPOND_USERNAME")
password = os.getenv("SPOND_PASSWORD")
group_id = os.getenv("SPOND_GROUP_ID")

# Check for missing environment variables
if not username or not password or not group_id:
    raise RuntimeError(
        "Missing required environment variables: SPOND_USERNAME, SPOND_PASSWORD, SPOND_GROUP_ID"
    )

# Initialize stored groups
app.state.groups = None

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
    attending = next_training.get("responses", {})
    logging.info(attending)
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


lock = Lock()


@app.get("/generate-random-groups/")
async def generate_random_groups(sim_amount: int):
    async with lock:
        s = spond.Spond(username=username, password=password)
        today = datetime.datetime.now()
        events = await s.get_events(group_id=group_id, min_start=today)
        if not events:
            raise HTTPException(
                status_code=404, detail="No upcoming events found.")

        next_training = events[0]
        attendies = await all_attendies(next_training)
        groups = await split_into_random(sim_amount, attendies)

        app.state.groups = groups
        app.state.generated_at = datetime.datetime.now().isoformat()

        return {"groups": groups}


@app.get("/get-date")
async def get_date():
    s = spond.Spond(username=username, password=password)

    # Fetch events
    today = datetime.datetime.now()
    events = await s.get_events(group_id=group_id, min_start=today)

    if not events:
        raise HTTPException(
            status_code=404, detail="No upcoming events found.")

    next_training = events[0]
    iso_datetime = next_training["startTimestamp"]
    parsed_datetime = datetime.datetime.strptime(
        iso_datetime, "%Y-%m-%dT%H:%M:%SZ")
    formatted_date = parsed_datetime.strftime("%d.%m.%Y")
    return {"date": formatted_date}


@app.get("/groups/")
async def get_groups():
    if app.state.groups is None:
        raise HTTPException(status_code=404, detail="No groups generated yet.")
    return JSONResponse(
        content={"groups": app.state.groups},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
