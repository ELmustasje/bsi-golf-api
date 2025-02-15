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
