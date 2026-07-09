import asyncio
import logging
import os
from datetime import date as _date
from pathlib import Path
from typing import Any, Optional

import asyncpg
from passlib.context import CryptContext

logger = logging.getLogger(__name__)


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

    async def connect(self, *, retries: int = 5, delay: float = 2.0) -> None:
        """Cria o pool asyncpg com backoff exponencial.

        Cobre cold-start do Supabase/Neon onde o pooler pode demorar ~10 s
        antes de aceitar conexões após um período de inatividade.
        """
        if self._pool is not None:
            return
        for attempt in range(retries):
            try:
                self._pool = await asyncpg.create_pool(
                    dsn=self.dsn,
                    min_size=self._min_size,
                    max_size=self._max_size,
                    statement_cache_size=self._statement_cache_size,
                    command_timeout=self._command_timeout,
                )
                return
            except Exception as exc:
                if attempt >= retries - 1:
                    raise
                wait = delay * (2 ** attempt)
                logger.warning(
                    "DB connect failed (attempt %d/%d): %s — retry in %.1fs",
                    attempt + 1, retries, exc, wait,
                )
                await asyncio.sleep(wait)

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
        """Aplica schema.sql, migrando do esquema antigo quando necessário.

        O esquema antigo tinha `amostras(measurements, ...)` e `relatorios`
        sem `user_id`. Como essas tabelas nunca foram populadas em produção
        (o pipeline gravava em filesystem), aqui detectamos a presença de
        `amostras` SEM coluna `user_id` e dropamos antes de aplicar o novo
        schema. `users` é preservado.
        """
        await self.connect()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    EXISTS(
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'amostras'
                    ) AS amostras_existe,
                    EXISTS(
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'amostras'
                          AND column_name = 'user_id'
                    ) AS amostras_tem_user_id,
                    EXISTS(
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'resultados'
                    ) AS resultados_existe,
                    EXISTS(
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'resultados'
                          AND column_name = 'user_id'
                    ) AS resultados_tem_user_id
                """
            )

            esquema_antigo = (
                row["amostras_existe"] and not row["amostras_tem_user_id"]
            ) or (
                row["resultados_existe"] and not row["resultados_tem_user_id"]
            )

            if esquema_antigo:
                await conn.execute("DROP TABLE IF EXISTS resultados CASCADE")
                await conn.execute("DROP TABLE IF EXISTS amostras CASCADE")
                await conn.execute("DROP TABLE IF EXISTS relatorios CASCADE")

            sql = load_schema_sql()
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

    # ── Stream de medições (Socket.IO) ────────────────────────────────

    async def salvar_medicao_stream(
        self,
        canal: str,
        chart: Optional[str],
        payload: dict,
    ) -> int:
        """Grava uma medição bruta vinda do RPi. Fire-and-forget no caller."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO medicoes_stream (canal, chart, payload)
                VALUES ($1, $2, $3::jsonb)
                RETURNING id
                """,
                canal,
                chart,
                payload if isinstance(payload, str) else __import__("json").dumps(payload),
            )

    async def ultimas_medicoes_stream(
        self,
        canal: str,
        limite: int,
    ) -> list[dict]:
        """Últimos `limite` pontos do canal, em ordem cronológica crescente."""
        if limite <= 0:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT payload FROM medicoes_stream
                WHERE canal = $1
                ORDER BY received_at DESC
                LIMIT $2
                """,
                canal,
                limite,
            )
        import json as _json

        payloads: list[dict] = []
        for r in reversed(rows):
            p = r["payload"]
            if isinstance(p, str):
                p = _json.loads(p)
            payloads.append(p)
        return payloads

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

    # ── Medições por período (stream diário/mensal) ────────────────────

    async def medicoes_do_dia(
        self,
        data_brt: str,
        canal: str = "default",
    ) -> list[dict]:
        """Pontos de medicoes_stream de um dia em BRT (formato YYYY-MM-DD).

        Converte o intervalo para UTC internamente usando o offset fixo
        UTC-3. Para produção com DST real usar ZoneInfo no caller.
        """
        import json as _json

        sql = """
            SELECT id, chart, payload, received_at
            FROM medicoes_stream
            WHERE canal = $1
              AND received_at >= ($2::date AT TIME ZONE 'America/Sao_Paulo')
              AND received_at <  (($2::date + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo')
            ORDER BY received_at
        """
        data = _date.fromisoformat(data_brt)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, canal, data)
        resultado = []
        for r in rows:
            p = r["payload"]
            if isinstance(p, str):
                p = _json.loads(p)
            resultado.append({
                "id": r["id"],
                "chart": r["chart"],
                "payload": p,
                "received_at": r["received_at"].isoformat(),
            })
        return resultado

    async def medicoes_do_periodo(
        self,
        inicio_brt: str,
        fim_brt: str,
        canal: str = "default",
    ) -> list[dict]:
        """Pontos de medicoes_stream entre inicio e fim (YYYY-MM-DD, inclusive, em BRT)."""
        import json as _json

        sql = """
            SELECT id, chart, payload, received_at
            FROM medicoes_stream
            WHERE canal = $1
              AND received_at >= ($2::date AT TIME ZONE 'America/Sao_Paulo')
              AND received_at <  (($3::date + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo')
            ORDER BY received_at
        """
        inicio = _date.fromisoformat(inicio_brt)
        fim = _date.fromisoformat(fim_brt)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, canal, inicio, fim)
        resultado = []
        for r in rows:
            p = r["payload"]
            if isinstance(p, str):
                p = _json.loads(p)
            resultado.append({
                "id": r["id"],
                "chart": r["chart"],
                "payload": p,
                "received_at": r["received_at"].isoformat(),
            })
        return resultado

    # ── Relatórios periódicos ─────────────────────────────────────────

    async def salvar_relatorio_periodico(
        self,
        tipo: str,
        periodo: str,
        dados: dict,
        canal: str = "default",
        charts: Optional[dict] = None,
        pdf: Optional[bytes] = None,
    ) -> int:
        import json as _json

        sql = """
            INSERT INTO relatorios_periodicos (tipo, periodo, canal, dados, charts, pdf)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6)
            ON CONFLICT (tipo, periodo, canal) DO UPDATE
                SET dados     = EXCLUDED.dados,
                    charts    = EXCLUDED.charts,
                    pdf       = EXCLUDED.pdf,
                    gerado_em = NOW()
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                sql,
                tipo,
                periodo,
                canal,
                _json.dumps(dados),
                _json.dumps(charts) if charts is not None else None,
                pdf,
            )

    async def ultimo_relatorio_periodico(
        self,
        tipo: str,
        canal: str = "default",
    ) -> Optional[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tipo, periodo, canal, dados, charts, pdf, gerado_em
                FROM relatorios_periodicos
                WHERE tipo = $1 AND canal = $2
                ORDER BY gerado_em DESC
                LIMIT 1
                """,
                tipo,
                canal,
            )
        return dict(row) if row else None

    async def relatorio_periodico_por_periodo(
        self,
        tipo: str,
        periodo: str,
        canal: str = "default",
    ) -> Optional[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tipo, periodo, canal, dados, charts, pdf, gerado_em
                FROM relatorios_periodicos
                WHERE tipo = $1 AND periodo = $2 AND canal = $3
                """,
                tipo,
                periodo,
                canal,
            )
        return dict(row) if row else None

    async def listar_relatorios_periodicos(
        self,
        tipo: str,
        canal: str = "default",
        limite: int = 30,
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, tipo, periodo, canal, gerado_em
                FROM relatorios_periodicos
                WHERE tipo = $1 AND canal = $2
                ORDER BY gerado_em DESC
                LIMIT $3
                """,
                tipo,
                canal,
                limite,
            )
        return [dict(r) for r in rows]
