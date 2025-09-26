"""In-memory runtime store for attendees and groups."""
from __future__ import annotations

import copy
import json
from asyncio import Lock
from pathlib import Path
from typing import Any, List, Optional

from fastapi import HTTPException


class InMemoryDataStore:
    """Persist attendees and groups in memory with seed fallbacks."""

    def __init__(self, attendees_seed: Path, groups_seed: Path | None = None) -> None:
        self._lock = Lock()
        self._attendees_seed = attendees_seed
        self._groups_seed = groups_seed
        self._attendees: Optional[List[Any]] = None
        self._groups: Optional[List[Any]] = None

    async def get_attendees(self) -> List[Any]:
        """Return the current attendees, seeding from disk on first use."""

        async with self._lock:
            if self._attendees is None:
                self._attendees = self._load_seed(self._attendees_seed, "Attendees")
            return copy.deepcopy(self._attendees)

    async def replace_attendees(self, attendees: List[Any]) -> None:
        """Replace the stored attendees with the provided list."""

        if not isinstance(attendees, list):
            raise HTTPException(
                status_code=500, detail="Attendees payload must be a JSON array (list)."
            )
        async with self._lock:
            self._attendees = copy.deepcopy(attendees)

    async def get_groups(self) -> List[Any]:
        """Return the current groups, seeding from disk on first use."""

        async with self._lock:
            if self._groups is None:
                self._groups = (
                    self._load_seed(self._groups_seed, "Groups")
                    if self._groups_seed is not None
                    else []
                )
            return copy.deepcopy(self._groups)

    async def replace_groups(self, groups: List[Any]) -> None:
        """Replace the stored groups with the provided list."""

        if not isinstance(groups, list):
            raise HTTPException(
                status_code=500, detail="Groups payload must be a JSON array (list)."
            )
        async with self._lock:
            self._groups = copy.deepcopy(groups)

    def _load_seed(self, path: Path, kind: str) -> List[Any]:
        if not path.exists():
            raise HTTPException(
                status_code=500, detail=f"{kind} seed file not found: {path}"
            )
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=500, detail=f"Invalid JSON in {path.name}: {exc}"
            ) from exc

        if not isinstance(data, list):
            raise HTTPException(
                status_code=500,
                detail=f"{path.name} seed must contain a JSON array (list).",
            )
        return data


MODULE_DIR = Path(__file__).resolve().parent
store = InMemoryDataStore(MODULE_DIR / "attendees.json")
