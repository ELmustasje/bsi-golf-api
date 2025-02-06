import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import random
import datetime
import os
from asyncio import Lock

logging.basicConfig(level=logging.INFO)

app = FastAPI()
lock = Lock()
app.state.groups = None


def read_excel_files(directory):
    attendees = []
    for filename in os.listdir(directory):
        if filename.endswith(".xlsx"):
            file_path = os.path.join(directory, filename)
            df = pd.read_excel(file_path)
            if "First Name" in df.columns and "Last Name" in df.columns:
                attendees.extend(
                    list(zip(df["First Name"].astype(str), df["Last Name"].astype(str)))
                )
    return attendees


def split_into_random(sim_amount, attendees):
    if sim_amount <= 0:
        raise ValueError("sim_amount must be greater than 0.")
    if not attendees:
        raise ValueError("attendees list cannot be empty.")

    random.shuffle(attendees)
    groups = [[] for _ in range(sim_amount)]
    for i, attendee in enumerate(attendees):
        groups[i % sim_amount].append(attendee)
    return groups


@app.get("/generate-random-groups/")
async def generate_random_groups(sim_amount: int):
    async with lock:
        try:
            directory = "./xlsx_files"  # Folder containing all Excel files
            attendees = read_excel_files(directory)
            groups = split_into_random(sim_amount, attendees)

            app.state.groups = groups
            app.state.generated_at = datetime.datetime.now().isoformat()

            return {"groups": groups}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/groups/")
async def get_groups():
    if app.state.groups is None:
        raise HTTPException(status_code=404, detail="No groups generated yet.")
    return JSONResponse(
        content={"groups": app.state.groups},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/")
async def root():
    return {"message": "Excel-based grouping API is running!"}
