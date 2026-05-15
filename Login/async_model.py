import os
from typing import Optional

import asyncpg
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def get_db_dsn_from_env() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_DSN")


CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
"""


class AsyncDBUserManager:
    """Asynchronous user manager using asyncpg.

    Passwords are hashed with pbkdf2_sha256 via passlib before storage.
    Call `ensure_schema()` once at app startup before serving requests.
    """

    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("A PostgreSQL DSN must be provided")
        self.dsn = dsn

    async def ensure_schema(self) -> None:
        conn = await asyncpg.connect(dsn=self.dsn)
        try:
            await conn.execute(CREATE_USERS_TABLE)
        finally:
            await conn.close()

    async def add_user(self, username: str, password: str) -> None:
        hashed = pwd_context.hash(password)
        conn = await asyncpg.connect(dsn=self.dsn)
        try:
            await conn.execute(
                "INSERT INTO users (username, password) VALUES ($1, $2)", username, hashed
            )
        except asyncpg.exceptions.UniqueViolationError:
            raise ValueError("User already exists")
        finally:
            await conn.close()

    async def remove_user(self, username: str) -> None:
        conn = await asyncpg.connect(dsn=self.dsn)
        try:
            await conn.execute("DELETE FROM users WHERE username = $1", username)
        finally:
            await conn.close()

    async def authenticate(self, username: str, password: str) -> bool:
        conn = await asyncpg.connect(dsn=self.dsn)
        try:
            row = await conn.fetchrow("SELECT password FROM users WHERE username = $1", username)
        finally:
            await conn.close()
        if not row:
            return False
        return pwd_context.verify(password, row["password"])
