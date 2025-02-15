import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import random
import datetime
import os
import json
from fastapi.middleware.cors import CORSMiddleware
from asyncio import Lock

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Allow all origins, methods, and headers (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

lock = Lock()
GROUPS_FILE = "groups.json"


def read_excel_files(directory):
    """Reads attendees from multiple Excel files in the directory."""
    attendees = []
    for filename in os.listdir(directory):
        if filename.endswith(".xlsx"):
            file_path = os.path.join(directory, filename)

            try:
                df = pd.read_excel(file_path, header=None)

                # Find the start and end indices dynamically
                start_index = (
                    df[df[0].astype(str).str.contains("Deltar", na=False)].index[0] + 2
                )
                end_index = df[
                    df[0].astype(str).str.contains("Ikke svart|Kommer ikke", na=False)
                ].index[0]

                # Extract the names
                attendees.extend(df.iloc[start_index:end_index, 0].dropna().tolist())
            except Exception as e:
                logging.error(f"Error reading file {filename}: {e}")

    return attendees


def split_into_random(sim_amount, attendees):
    """Splits attendees into random groups."""
    if sim_amount <= 0:
        raise ValueError("sim_amount must be greater than 0.")
    if not attendees:
        raise ValueError("attendees list cannot be empty.")

    random.shuffle(attendees)
    groups = [[] for _ in range(sim_amount)]
    for i, attendee in enumerate(attendees):
        groups[i % sim_amount].append(attendee)

    return groups


def save_groups_to_file(groups):
    """Saves the groups to a JSON file."""
    data = {"generated_at": datetime.datetime.now().isoformat(), "groups": groups}
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def read_groups_from_file():
    """Reads groups from the JSON file."""
    if not os.path.exists(GROUPS_FILE):
        raise HTTPException(status_code=404, detail="Groups file not found.")

    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error reading groups file.")


@app.get("/generate-random-groups/")
async def generate_random_groups(sim_amount: int):
    """Generates random groups, saves them to a file, and returns them."""
    async with lock:
        try:
            directory = "./xlsx_files"  # Folder containing all Excel files
            attendees = read_excel_files(directory)
            groups = split_into_random(sim_amount, attendees)

            # Save to file
            save_groups_to_file(groups)

            return {"groups": groups}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/groups/")
async def get_groups():
    """Reads the groups from a file and returns them."""
    return JSONResponse(
        content=read_groups_from_file(),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/")
async def root():
    return {"message": "Excel-based grouping API is running!"}
