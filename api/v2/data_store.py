"""PostgreSQL-backed runtime store for attendees and groups."""
from __future__ import annotations

import copy
import os
from asyncio import Lock
from typing import Any, List

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import AsyncConnectionPool


class PostgresDataStore:
    """Persist attendees and groups in PostgreSQL as JSON payloads."""

    TABLE_NAME = "api_state"
    ATTENDEES_KEY = "attendees"
    GROUPS_KEY = "groups"

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: AsyncConnectionPool | None = None
        self._pool_lock = Lock()

    async def get_attendees(self) -> List[Any]:
        """Return the current attendees stored in the database."""

        data = await self._fetch_list(self.ATTENDEES_KEY)
        return copy.deepcopy(data)

    async def replace_attendees(self, attendees: List[Any]) -> None:
        """Replace the stored attendees with the provided list."""

        await self._store_list(self.ATTENDEES_KEY, attendees)

    async def get_groups(self) -> List[Any]:
        """Return the current simulator groups stored in the database."""

        data = await self._fetch_list(self.GROUPS_KEY)
        return copy.deepcopy(data)

    async def replace_groups(self, groups: List[Any]) -> None:
        """Replace the stored groups with the provided list."""

        await self._store_list(self.GROUPS_KEY, groups)

    async def _store_list(self, key: str, payload: List[Any]) -> None:
        if not isinstance(payload, list):
            raise HTTPException(
                status_code=500,
                detail=f"{key.capitalize()} payload must be a JSON array (list).",
            )

        pool = await self._ensure_pool()

        try:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"""
                        INSERT INTO {self.TABLE_NAME} (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key) DO UPDATE
                        SET value = EXCLUDED.value,
                            updated_at = NOW()
                        """,
                        (key, Json(copy.deepcopy(payload))),
                    )
        except psycopg.Error as exc:  # pragma: no cover - surface as HTTP error
            raise HTTPException(
                status_code=500, detail="Database error while saving data."
            ) from exc

    async def _fetch_list(self, key: str) -> List[Any]:
        pool = await self._ensure_pool()

        try:
            async with pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        f"SELECT value FROM {self.TABLE_NAME} WHERE key = %s", (key,)
                    )
                    row = await cur.fetchone()
        except psycopg.Error as exc:  # pragma: no cover - surface as HTTP error
            raise HTTPException(
                status_code=500, detail="Database error while loading data."
            ) from exc

        value = row["value"] if row is not None else []
        if value is None:
            value = []
        if not isinstance(value, list):
            raise HTTPException(
                status_code=500,
                detail=f"Stored {key} data must be a JSON array (list).",
            )
        return value

    async def _ensure_pool(self) -> AsyncConnectionPool:
        if self._pool is None:
            async with self._pool_lock:
                if self._pool is None:
                    try:
                        self._pool = AsyncConnectionPool(
                            self._dsn,
                            min_size=1,
                            max_size=5,
                            kwargs={"autocommit": True},
                        )
                        await self._pool.open()
                        await self._initialise_schema()
                    except psycopg.Error as exc:  # pragma: no cover - init failure
                        raise HTTPException(
                            status_code=500,
                            detail="Could not connect to the database.",
                        ) from exc
        assert self._pool is not None  # for type checkers
        return self._pool

    async def _initialise_schema(self) -> None:
        assert self._pool is not None
        try:
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                            key TEXT PRIMARY KEY,
                            value JSONB NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
        except psycopg.Error as exc:  # pragma: no cover - init failure
            raise HTTPException(
                status_code=500,
                detail="Failed to initialise database schema.",
            ) from exc


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_j5tlyPDaX4VF@ep-cold-sky-ab325omy-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
)

store = PostgresDataStore(DATABASE_URL)
