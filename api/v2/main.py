import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from asyncio import Lock

from utils.spond import get_next_training_attendees

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


@app.get("/attendees/")
async def get_attendees():
    """Reads the attendees from a file and returns them."""
    attendees = await get_next_training_attendees()

    return JSONResponse(
        content=attendees,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/")
async def root():
    return {"message": "API v2 is running!"}
