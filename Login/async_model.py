import os
from pathlib import Path
from typing import Any, Optional

import asyncpg
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def get_db_dsn_from_env() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_DSN")


DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def load_schema_sql() -> str:
    path = Path(os.environ.get("SCHEMA_PATH", DEFAULT_SCHEMA_PATH))
    return path.read_text(encoding="utf-8")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


CHARTS_VALIDAS = {"XR", "P", "U", "IMR"}


class AsyncDBUserManager:
    """Pool asyncpg compartilhado + acesso a usuários, amostras e resultados.

    Para Supabase Pooler em modo Transaction (pgbouncer) é necessário
    `ASYNCPG_STATEMENT_CACHE_SIZE=0` (default aqui).
    """

    def __init__(
        self,
        dsn: str,
        *,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        statement_cache_size: Optional[int] = None,
        command_timeout: Optional[float] = None,
    ):
        if not dsn:
            raise ValueError("A PostgreSQL DSN must be provided")
        self.dsn = dsn
        self._min_size = min_size if min_size is not None else _env_int("DB_POOL_MIN", 1)
        self._max_size = max_size if max_size is not None else _env_int("DB_POOL_MAX", 5)
        self._statement_cache_size = (
            statement_cache_size
            if statement_cache_size is not None
            else _env_int("ASYNCPG_STATEMENT_CACHE_SIZE", 0)
        )
        self._command_timeout = command_timeout if command_timeout is not None else 10.0
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            statement_cache_size=self._statement_cache_size,
            command_timeout=self._command_timeout,
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Pool not initialized — call connect() first")
        return self._pool

    async def ping(self) -> bool:
        await self.connect()
        async with self.pool.acquire() as conn:
            return (await conn.fetchval("SELECT 1")) == 1

    async def ensure_schema(self) -> None:
        sql = load_schema_sql()
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    # ── Users ─────────────────────────────────────────────────────────

    async def add_user(self, username: str, password: str) -> None:
        hashed = pwd_context.hash(password)
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO users (username, password) VALUES ($1, $2)",
                    username,
                    hashed,
                )
        except asyncpg.exceptions.UniqueViolationError:
            raise ValueError("User already exists")

    async def remove_user(self, username: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM users WHERE username = $1", username)

    async def authenticate(self, username: str, password: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT password FROM users WHERE username = $1", username
            )
        if not row:
            # Verificação de hash dummy para não vazar existência de user
            # por timing.
            try:
                pwd_context.dummy_verify()
            except AttributeError:
                pass
            return False
        return pwd_context.verify(password, row["password"])

    async def get_user_id(self, username: str) -> Optional[int]:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT id FROM users WHERE username = $1", username
            )

    # ── Amostras ──────────────────────────────────────────────────────

    async def salvar_amostra(
        self, user_id: int, chart: str, payload: dict
    ) -> int:
        chart = chart.upper()
        if chart not in CHARTS_VALIDAS:
            raise ValueError(f"chart inválida: {chart}")
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO amostras (user_id, chart, payload)
                VALUES ($1, $2, $3::jsonb)
                RETURNING id
                """,
                user_id,
                chart,
                payload if isinstance(payload, str) else __import__("json").dumps(payload),
            )

    async def amostras_do_usuario(
        self, user_id: int, chart: Optional[str] = None
    ) -> list[dict]:
        if chart:
            sql = (
                "SELECT id, chart, payload, criado_em FROM amostras "
                "WHERE user_id = $1 AND chart = $2 ORDER BY criado_em"
            )
            args = [user_id, chart.upper()]
        else:
            sql = (
                "SELECT id, chart, payload, criado_em FROM amostras "
                "WHERE user_id = $1 ORDER BY criado_em"
            )
            args = [user_id]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]

    # ── Resultados ────────────────────────────────────────────────────

    async def salvar_resultado(
        self,
        user_id: int,
        chart: str,
        dados: dict,
        pdf: Optional[bytes] = None,
        amostra_id: Optional[int] = None,
    ) -> int:
        chart = chart.upper()
        if chart not in CHARTS_VALIDAS:
            raise ValueError(f"chart inválida: {chart}")
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO resultados (user_id, amostra_id, chart, dados, pdf)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                RETURNING id
                """,
                user_id,
                amostra_id,
                chart,
                dados if isinstance(dados, str) else __import__("json").dumps(dados),
                pdf,
            )

    async def ultimo_resultado(
        self, user_id: int, chart: str
    ) -> Optional[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, chart, dados, pdf, gerado_em
                FROM resultados
                WHERE user_id = $1 AND chart = $2
                ORDER BY gerado_em DESC
                LIMIT 1
                """,
                user_id,
                chart.upper(),
            )
        return dict(row) if row else None
